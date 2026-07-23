"""Collector 采集服务（Phase 3A：采集 → 入库 → 自动 AI 分析闭环）。

职责：
  1. 调度各 Collector.fetch() 拿到标准化 dict 列表。
  2. 按 url 去重（url 为空时退回 title+publish_time 辅助判断），跳过已存在项。
  3. 新建 Opinion（默认 risk_score=0 / sentiment=neutral / analysis_status=pending）。
  4. 调用 RuleFallbackProvider.analyze(title, content) 做规则降级分析，生成
     「系统研判报告」并写回字段 + 状态流转。DeepSeek 不在采集阶段调用
     （仅由用户手动「触发 AI 分析」时调用，见 api/analysis.py）。
  5. 单条 AI 失败隔离：该条置 analysis_status="failed"（保留数据库记录），
     不影响其余数据；失败计数 failed = created - analyzed。

设计约束（来自用户确认）：
- 采集阶段直接复用 RuleFallbackProvider（规则降级）生成系统研判报告，
  不抽取公共 AIAnalysisHelper（MVP 快速验证）；但已在下方标注 TODO Phase 4 待抽取。
- 采集阶段不调用 DeepSeek / 不依赖 AIService，避免消耗 API 额度。
- 采集状态存**模块级内存变量**（见 _COLLECTOR_STATUS），重启丢失、不持久化。
  # Phase 3A temporary implementation.
  # Persistent collector task history is postponed.
  # Future: 若增加定时采集，再设计 collector_runs 表。
- 不修改数据库结构 / 不新增迁移 / 不引入 Celery / Redis / 定时任务。
"""
from __future__ import annotations

import logging
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable, List, Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

from app.collectors.base import BaseCollector
from app.collectors.government_collector import GovernmentCollector
from app.collectors.registry import resolve_collectors, resolve_collectors_verbose
from app.core.config import settings
from app.models.opinion import Opinion
from app.models.region import Region
from app.models.collector_run import CollectorRun
from app.services.ai.fallback import RuleFallbackProvider
from app.services.keyword_service import get_monitoring_keywords, get_sensitive_keywords

# ---------------------------------------------------------------------------
# Phase 3A temporary implementation.
# Persistent collector task history is postponed.
# Future: if scheduled collection is added, design a `collector_runs` table.
# ---------------------------------------------------------------------------
_COLLECTOR_STATUS: dict = {
    "last_run": None,   # datetime | None，最近一次采集时间
    "total_collected": 0,  # int，累计采集（本次进程内）
    "collector_type": None,  # str | None，最近一次采集方式（government/mock）
}

# Phase 3B：政府网站采集防抖时间戳（模块级内存，重启丢失）。
# 每次 government 采集后更新；THROTTLE_SECONDS 内重复触发 → CollectorThrottled。
_GOV_LAST_RUN_AT: Optional[datetime] = None
THROTTLE_SECONDS = 5.0


class CollectorThrottled(Exception):
    """政府网站采集触发过于频繁（5 秒防抖），由 API 层转 429。"""


def reset_gov_throttle() -> None:
    """重置政府采集防抖时间戳（供测试使用）。"""
    global _GOV_LAST_RUN_AT
    _GOV_LAST_RUN_AT = None


# resolve_collectors 已迁至 collectors/registry.py（表驱动装配 + 灰度回退）。
# 此处重新导出，保持 app.collectors.service.resolve_collectors 可用（测试依赖）。





@dataclass
class CollectorRunResult:
    """单次采集运行结果。"""

    created: int = 0    # 本次实际新增 Opinion 数量
    analyzed: int = 0   # AI 分析成功（completed）数量
    fetched_raw: int = 0  # 采集器实际抓取的原始舆情条数（去重前，fetch() 返回量）
    collector_type: str = ""  # 本次采集方式（government/mock）

    def finalize(self) -> "CollectorRunResult":
        # 失败 = 新增 - 分析成功；失败记录保留在数据库（status=failed）。
        self.failed = max(0, self.created - self.analyzed)
        return self

    # failed 经 finalize 计算后存在；声明占位避免 mypy 报未定义。
    failed: int = 0


def get_collector_status() -> dict:
    """返回采集状态（模块级内存，重启丢失；见上方 Phase 3A 注释）。"""
    return dict(_COLLECTOR_STATUS)


def reclaim_zombie_runs(db: Session, *, timeout_minutes: Optional[int] = None) -> int:
    """启动时对账：将超时仍 running 的历史 CollectorRun 回收为 failed。

    - 仅回收「开始时间早于 now - timeout」的记录，避免误判刚启动/仍在途的任务
      （应用启动时该进程内无任何采集在途，但阈值仍是安全保护）。
    - timeout 复用配置 ``collector_run_zombie_timeout_minutes``（集中定义，禁止散落 magic number）。
    - 不引入 Redis / Celery / 数据库锁服务等新组件（Phase 6 纪律）。
    - 回收原因明确写入 error_msg，便于采集日志定位。

    返回被回收的记录数。
    """
    if timeout_minutes is None:
        timeout_minutes = settings.collector_run_zombie_timeout_minutes
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=timeout_minutes)
    rows = (
        db.query(CollectorRun)
        .filter(CollectorRun.status == "running", CollectorRun.start_time < cutoff)
        .all()
    )
    for r in rows:
        r.status = "failed"
        r.error_msg = "采集进程重启或异常中断，原运行状态已超时回收"
        r.end_time = datetime.now(timezone.utc)
    if rows:
        db.commit()
    return len(rows)


class CollectorService:
    """采集闭环服务：fetch → 去重 → 建 Opinion → AI 分析 → 状态流转。"""

    def __init__(
        self,
        collectors: Optional[List[BaseCollector]] = None,
        region_id: Optional[int] = None,
        collector_type: Optional[str] = None,
    ) -> None:
        # 采集方式：显式传入 > Pydantic Settings（collector_type）。
        self.collector_type: str = (
            collector_type or settings.collector_type or "government"
        ).lower()
        # 默认采集器：按 collector_type 选择（government / mock）。
        # 也可显式注入 collectors（测试用），此时 collector_type 仍用于返回标识。
        self._collectors_injected: bool = collectors is not None
        self.collectors: List[BaseCollector] = (
            collectors if collectors is not None else resolve_collectors(collector_type=self.collector_type)
        )
        self.region_id: Optional[int] = region_id

        # 并发抓取时，多个采集器线程各自持有独立 DB 会话，但「查重 + 新建 Opinion」
        # 的临界区需串行化，避免不同源抓到相同 url 时重复入库。网络 I/O（fetch）
        # 在锁外并行，仅 DB 写入短暂串行，整体耗时≈最慢单个源而非各源之和。
        self._write_lock = threading.Lock()

        # TODO Phase 4:
        # extract shared opinion analysis workflow
        # reuse by manual analysis API and collector service

    def _uses_government(self) -> bool:
        """本次采集是否涉及政府网站（决定是否启用 5 秒防抖）。"""
        return any(isinstance(c, GovernmentCollector) for c in self.collectors)

    # ------------------------------------------------------------------
    # 内部工具
    # ------------------------------------------------------------------
    def _resolve_region_id(self, db: Session, collector: BaseCollector) -> int:
        """按采集器声明的 scope_region_codes 绑定区域（省→市→县）。

        - 取 scope 中最具体的 code（最长 = 县>市>省）；
        - scope 为空/None（国家级源，靠关键词过滤河北）→ 绑定河北省(130000)；
        - 若目标区域不存在，回退 130000，再回退任意区域（避免种子缺失时整体失败）。
        """
        codes = getattr(collector, "scope_region_codes", None)
        target_code = max(codes, key=len) if codes else None
        region = None
        if target_code:
            region = db.query(Region).filter(Region.code == target_code).first()
        if region is None:
            region = db.query(Region).filter(Region.code == "130000").first()
        if region is None:
            region = db.query(Region).first()
        if region is None:
            raise RuntimeError(
                "未配置任何区域（region），Collector 无法绑定 region_id；"
                "请先执行 init_db.py 初始化种子区域。"
            )
        return region.id

    def _already_exists(self, db: Session, item: dict) -> bool:
        """去重判断（以 opinions.url 为准；url 为空时退回 title+publish_time）。"""
        url = (item.get("url") or "").strip()
        if url:
            exists = db.query(Opinion).filter(Opinion.url == url).first()
            if exists is not None:
                return True
        # url 为空（或该 url 未命中）-> 用 title + publish_time 辅助判断
        title = (item.get("title") or "").strip()
        pub = item.get("publish_time")
        exists = (
            db.query(Opinion)
            .filter(
                Opinion.url == "",
                Opinion.title == title,
                Opinion.publish_time == pub,
            )
            .first()
        )
        return exists is not None

    # ------------------------------------------------------------------
    # 主流程
    # ------------------------------------------------------------------
    def collect_and_analyze(self, db: Session, trigger_type: str = "scheduled") -> CollectorRunResult:
        """执行一次采集 + 自动 AI 分析，返回运行结果（Phase 3 表驱动 + 按区域绑定）。

        - 未显式注入 collectors 时，按 db 中的 data_sources 表装配（灰度回退默认源）。
        - 每个采集器独立绑定其 scope_region_codes 对应的 region_id。
        - 5 秒防抖仅对政府网站采集生效。
        """
        global _GOV_LAST_RUN_AT

        # 表驱动装配（优先 data_sources 表，表空回退默认源）；注入模式不覆盖。
        # 装配失败的源（非法 config_json / 采集器构建异常）进入 failures，
        # 由 _record_assembly_failure 写入 CollectorRun(status=failed)，在采集日志中可见。
        run_start = datetime.now(timezone.utc)
        batch_id = uuid.uuid4().hex
        if not self._collectors_injected:
            resolved = resolve_collectors_verbose(db, self.collector_type)
            self.collectors = resolved.collectors
            for f in resolved.failures:
                self._record_assembly_failure(db, f, run_start, batch_id, trigger_type)

        # 监测关键词（采集过滤唯一权威源 = keywords 表；表空回退配置）。
        # 一次采集运行内只解析一次，注入到每个采集器的 fetch(keywords=...)。
        monitoring_kw = get_monitoring_keywords(db)

        # 5 秒防抖（仅政府网站采集）：距上次不足阈值 → 拒绝执行。
        if self._uses_government() and _GOV_LAST_RUN_AT is not None:
            elapsed = (datetime.now(timezone.utc) - _GOV_LAST_RUN_AT).total_seconds()
            if elapsed < THROTTLE_SECONDS:
                raise CollectorThrottled("collector running too frequently")

        result = CollectorRunResult(collector_type=self.collector_type)
        # 采集阶段默认使用规则降级路径生成「系统研判报告」，
        # 不调用 DeepSeek（节省额度；DeepSeek 仅由用户手动「触发 AI 分析」时调用）。

        for collector in self.collectors:
            sub = self._process_collector(db, collector, monitoring_kw, run_start, batch_id, trigger_type)
            result.fetched_raw += sub.fetched_raw
            result.created += sub.created
            result.analyzed += sub.analyzed
            result.failed += sub.failed

        result.finalize()

        # 4) 更新内存状态（Phase 3A 临时，重启丢失）
        now = datetime.now(timezone.utc)
        _COLLECTOR_STATUS["last_run"] = now
        _COLLECTOR_STATUS["total_collected"] += result.created
        _COLLECTOR_STATUS["collector_type"] = self.collector_type

        # 政府网站采集成功后更新防抖时间戳（供下次 5 秒判断）。
        if self._uses_government():
            _GOV_LAST_RUN_AT = now

        return result

    # ------------------------------------------------------------------
    # 单采集器处理（供顺序 / 并发两种主流程复用）
    # ------------------------------------------------------------------
    def _record_assembly_failure(
        self, db: Session, failure: dict, run_start: datetime, batch_id: str, trigger_type: str
    ) -> None:
        """将装配失败的源写入一条 CollectorRun（status=failed）。

        让"该源因配置/构建错误完全没有采集"的异常在采集日志与逐源历史中
        可见，而不是被装配环节静默丢弃。复用既有 collector_runs 表与
        collection-logs 聚合逻辑（按 batch_id 归并）。
        """
        name = failure.get("name") or failure.get("key") or "unknown"
        run = CollectorRun(
            collector_name=name,
            batch_id=batch_id,
            trigger_type=trigger_type,
            start_time=run_start,
            end_time=datetime.now(timezone.utc),
            status="failed",
            error_msg=failure.get("error") or "采集器装配失败",
        )
        db.add(run)
        db.commit()

    def _process_collector(
        self,
        db: Session,
        collector: BaseCollector,
        monitoring_kw: List[str],
        run_start: datetime,
        batch_id: str,
        trigger_type: str,
    ) -> "CollectorRunResult":
        """对单个采集器执行 fetch → 去重 → 建 Opinion → AI 分析 → 状态流转。

        返回该采集器的局部运行结果。注意：本方法内所有 DB 写入（查重+新建+
        分析写回）须在同一把实例锁 ``self._write_lock`` 下完成，以防并发抓取时
        不同源抓到同一 url 导致重复入库。
        """
        # 每个采集器独立记录一次采集运行（CollectorRun），用于审计与历史。
        run = CollectorRun(
            collector_name=collector.source_name,
            batch_id=batch_id,
            trigger_type=trigger_type,
            start_time=run_start,
            status="running",
        )
        db.add(run)
        db.commit()

        try:
            items = collector.fetch(keywords=monitoring_kw) or []
            # 统计采集器实际抓取的原始条数（去重前），供前端提示真实抓取量。
            fetched_raw = len(items)
            run.fetched_raw = fetched_raw

            # 按采集器声明的覆盖范围绑定区域（省/市/县）
            region_id = self._resolve_region_id(db, collector)

            # 每条 Opinion 的 AI 分析独立（无共享可变状态），逐采集器新建 Provider。
            # 敏感/风险词由 keywords 表（type='sensitive'）注入；无启用敏感词时
            # get_sensitive_keywords 自动回退内置 DEFAULT_KEYWORDS，风险评分零回归。
            ai = RuleFallbackProvider(keywords=get_sensitive_keywords(db))

            c_created = c_analyzed = c_failed = 0
            for item in items:
                # 1) 去重：已存在则跳过，不重复创建（临界区串行化）
                with self._write_lock:
                    if self._already_exists(db, item):
                        continue

                    # 2) 新建 Opinion（默认 pending，先落库保证失败也保留记录）
                    opinion = Opinion(
                        title=(item.get("title") or "").strip(),
                        content=item.get("content") or "",
                        source=(item.get("source") or "").strip() or collector.source_name,
                        url=(item.get("url") or "").strip(),
                        publish_time=item.get("publish_time"),
                        region_id=region_id,
                        risk_score=0,
                        sentiment="neutral",
                        analysis_status="pending",
                    )
                    try:
                        db.add(opinion)
                        db.commit()  # 先提交，确保失败记录不丢失
                    except IntegrityError:
                        # P1-2：数据库级唯一约束兜底（并发插入相同 url）。
                        # 视为已存在，跳过，绝不把正常重复冲突当作系统级异常导致整批失败。
                        db.rollback()
                        if self._already_exists(db, item):
                            continue
                        raise  # 非 url 唯一冲突的真实错误，按原样抛出
                c_created += 1

                # 3) AI 分析 + 写回（单条失败隔离；分析写回也在锁内，避免并发更新冲突）
                try:
                    analysis = ai.analyze(
                        f"标题：{opinion.title}\n正文：{opinion.content}"
                    )
                    opinion.summary = analysis.summary
                    opinion.sentiment = analysis.sentiment
                    opinion.risk_score = analysis.risk_score
                    opinion.keywords = ",".join(analysis.keywords)
                    opinion.analysis_suggestion = analysis.suggestion
                    opinion.analysis_status = "completed"
                    opinion.analysis_time = datetime.now(timezone.utc)
                    with self._write_lock:
                        db.commit()
                    c_analyzed += 1
                except Exception:
                    # 失败：保留该 Opinion 记录，仅状态置 failed（单条失败隔离，不影响其余）
                    db.rollback()
                    opinion.analysis_status = "failed"
                    db.add(opinion)
                    with self._write_lock:
                        db.commit()
                    c_failed += 1

            # 写回本次采集器运行结果
            run.created = c_created
            run.analyzed = c_analyzed
            run.failed = c_failed
            run.status = "success" if c_failed == 0 else "partial"
            run.end_time = datetime.now(timezone.utc)
            db.commit()

            return CollectorRunResult(
                collector_type=self.collector_type,
                fetched_raw=fetched_raw,
                created=c_created,
                analyzed=c_analyzed,
                failed=c_failed,
            )
        except Exception as exc:
            # P1-1：采集器级异常（fetch / 区域解析 / 循环内未捕获异常）必须最终落为 failed，
            # 不得让对应 CollectorRun 永久停留 running；error_msg 保留足够定位信息；
            # 不吞掉异常伪装成功——标记失败后重新抛出，原有调用方行为（异常上抛）不变。
            run.status = "failed"
            run.error_msg = f"{type(exc).__name__}: {exc}"[:2000]
            run.end_time = datetime.now(timezone.utc)
            try:
                db.commit()
            except Exception:
                db.rollback()
            raise

    # ------------------------------------------------------------------
    # 并发主流程（后台任务使用）：每个采集器独立线程 + 独立 DB 会话并行抓取
    # ------------------------------------------------------------------
    def collect_and_analyze_concurrent(
        self,
        session_factory,
        max_workers: int = 6,
        on_progress: Optional[Callable[[int, int, str], None]] = None,
        trigger_type: str = "manual",
        batch_id: Optional[str] = None,
    ) -> "CollectorRunResult":
        """并发版采集：各采集器在独立线程内 fetch（网络 I/O 并行），整体耗时≈最慢单源。

        - 表驱动装配与监测关键词解析在主线程完成（需 DB，仅读）；
        - 每个采集器线程使用 ``session_factory()`` 新建独立 Session（会话不跨线程）；
        - on_progress(done, total, source_name) 用于上报进度（后台任务轮询）。
        """
        global _GOV_LAST_RUN_AT

        # 表驱动装配（优先 data_sources 表，表空回退默认源）；注入模式不覆盖。
        # 装配失败的源写入 CollectorRun(failed)，在采集日志中可见。
        run_start = datetime.now(timezone.utc)
        batch_id = batch_id or uuid.uuid4().hex
        if not self._collectors_injected:
            resolve_db = session_factory()
            try:
                resolved = resolve_collectors_verbose(resolve_db, self.collector_type)
                self.collectors = resolved.collectors
                for f in resolved.failures:
                    self._record_assembly_failure(resolve_db, f, run_start, batch_id, trigger_type)
                resolve_db.commit()
            finally:
                resolve_db.close()

        # 监测关键词（采集过滤唯一权威源 = keywords 表；表空回退配置）。
        kw_db = session_factory()
        try:
            monitoring_kw = get_monitoring_keywords(kw_db)
        finally:
            kw_db.close()

        # 5 秒防抖（仅政府网站采集）：距上次不足阈值 → 拒绝执行。
        if self._uses_government() and _GOV_LAST_RUN_AT is not None:
            elapsed = (datetime.now(timezone.utc) - _GOV_LAST_RUN_AT).total_seconds()
            if elapsed < THROTTLE_SECONDS:
                raise CollectorThrottled("collector running too frequently")

        if not self.collectors:
            result = CollectorRunResult(collector_type=self.collector_type)
            result.finalize()
            return result

        total = len(self.collectors)

        def _work(collector: BaseCollector) -> "CollectorRunResult":
            cdb = session_factory()
            try:
                return self._process_collector(cdb, collector, monitoring_kw, run_start, batch_id, trigger_type)
            finally:
                cdb.close()

        merged = CollectorRunResult(collector_type=self.collector_type)
        done = 0
        with ThreadPoolExecutor(max_workers=max_workers) as ex:
            futures = {ex.submit(_work, c): c for c in self.collectors}
            for fut in as_completed(futures):
                collector = futures[fut]
                try:
                    sub = fut.result()
                except Exception:
                    logger.exception("采集器 %s 执行异常", collector.source_name)
                    sub = CollectorRunResult(collector_type=self.collector_type)
                merged.fetched_raw += sub.fetched_raw
                merged.created += sub.created
                merged.analyzed += sub.analyzed
                merged.failed += sub.failed
                done += 1
                if on_progress is not None:
                    on_progress(done, total, getattr(collector, "source_name", ""))

        merged.finalize()

        # 更新内存状态（Phase 3A 临时，重启丢失）
        now = datetime.now(timezone.utc)
        _COLLECTOR_STATUS["last_run"] = now
        _COLLECTOR_STATUS["total_collected"] += merged.created
        _COLLECTOR_STATUS["collector_type"] = self.collector_type

        # 政府网站采集成功后更新防抖时间戳（供下次 5 秒判断）。
        if self._uses_government():
            _GOV_LAST_RUN_AT = now

        return merged
