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
from typing import Callable, Collection, List, Optional

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
from app.services.keyword_service import (
    get_monitoring_keywords,
    get_monitoring_keywords_grouped,
    get_severity_keywords,
    get_sensitive_keywords,
)
from app.services.risk_engine import RISK_MODEL_VERSION, RiskEngine
from app.services.opinion_admission_service import OpinionAdmissionService
from app.services.opinion_region_service import OpinionRegionService

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
    comments_seen: int = 0  # 采集阶段识别到的评论数量（评论不创建 Opinion）
    comments_skipped: int = 0  # 已跳过、未进入 Opinion 的评论数量
    admission_filtered: int = 0  # 微博正文因准入规则拒绝的数量
    collector_type: str = ""  # 本次采集方式（government/mock）

    upstream_total: Optional[int] = None
    upstream_returned: int = 0
    acknowledged: int = 0
    unconfirmed: int = 0
    ack_status: str = "not_applicable"

    def finalize(self) -> "CollectorRunResult":
        # 失败 = 新增 - 分析成功；失败记录保留在数据库（status=failed）。
        # Keep collector-level exceptions in the batch result even when
        # other collectors created and analyzed an equal number of opinions.
        self.failed = max(self.failed, self.created - self.analyzed, 0)
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
        include_data_source_keys: Optional[Collection[str]] = None,
        exclude_data_source_keys: Optional[Collection[str]] = None,
    ) -> None:
        # 采集方式：显式传入 > Pydantic Settings（collector_type）。
        self.collector_type: str = (
            collector_type or settings.collector_type or "government"
        ).lower()
        # 默认采集器：按 collector_type 选择（government / mock）。
        # 也可显式注入 collectors（测试用），此时 collector_type 仍用于返回标识。
        self._collectors_injected: bool = collectors is not None
        self.include_data_source_keys = (
            frozenset(include_data_source_keys)
            if include_data_source_keys is not None
            else None
        )
        self.exclude_data_source_keys = (
            frozenset(exclude_data_source_keys)
            if exclude_data_source_keys is not None
            else None
        )
        self.collectors: List[BaseCollector] = (
            collectors
            if collectors is not None
            else resolve_collectors(
                collector_type=self.collector_type,
                include_data_source_keys=self.include_data_source_keys,
                exclude_data_source_keys=self.exclude_data_source_keys,
            )
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
    def _resolve_region_id(self, db: Session, collector: BaseCollector) -> Optional[int]:
        """按采集器声明的 scope_region_codes 绑定区域（省→市→县）。

        - 取 scope 中最具体的 code（最长 = 县>市>省）；
        - scope 为空/None/ALL（国家级源）不再回退廊坊市；
        - 若目标区域不存在，返回 None，由 item 级地区准入处理。
        """
        codes = getattr(collector, "scope_region_codes", None)
        if not codes:
            return None
        target_code = max(codes, key=len) if codes else None
        region = None
        if target_code:
            region = db.query(Region).filter(Region.code == target_code).first()
        return region.id if region is not None else None

    def _already_exists(self, db: Session, item: dict) -> bool:
        """去重判断（external_id 优先；其次 opinions.url；url 为空时退回 title+publish_time）。

        Phase Weibo-1：社媒条目携带平台唯一 ID（如微博 mid）时以
        (source_type, external_id) 为第一优先键——比 url 更稳定（同一条微博
        可能出现短链/长链两种 url）。既有采集器不传 external_id，行为不变。
        """
        ext = (item.get("external_id") or "").strip() if item.get("external_id") else ""
        if ext:
            q = db.query(Opinion).filter(Opinion.external_id == ext)
            stype = item.get("source_type")
            if stype:
                q = q.filter(Opinion.source_type == stype)
            if q.first() is not None:
                return True
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
            resolved = resolve_collectors_verbose(
                db,
                self.collector_type,
                include_data_source_keys=self.include_data_source_keys,
                exclude_data_source_keys=self.exclude_data_source_keys,
            )
            self.collectors = resolved.collectors
            for f in resolved.failures:
                self._record_assembly_failure(db, f, run_start, batch_id, trigger_type)

        # 监测关键词（采集过滤唯一权威源 = keywords 表；表空回退配置）。
        # 一次采集运行内只解析一次：
        #  - monitoring_kw：扁平列表，向下兼容 keywords= 旧链路；
        #  - region_kw / topic_kw：按 category 分组，驱动「地域前置过滤 + 主题增强」新链路。
        monitoring_kw = get_monitoring_keywords(db)
        grouped = get_monitoring_keywords_grouped(db)
        region_kw: List[str] = grouped.get("地域", [])
        topic_kw: List[str] = grouped.get("主题", [])

        # 5 秒防抖（仅政府网站采集）：距上次不足阈值 → 拒绝执行。
        if self._uses_government() and _GOV_LAST_RUN_AT is not None:
            elapsed = (datetime.now(timezone.utc) - _GOV_LAST_RUN_AT).total_seconds()
            if elapsed < THROTTLE_SECONDS:
                raise CollectorThrottled("collector running too frequently")

        result = CollectorRunResult(collector_type=self.collector_type)
        # 采集阶段默认使用规则降级路径生成「系统研判报告」，
        # 不调用 DeepSeek（节省额度；DeepSeek 仅由用户手动「触发 AI 分析」时调用）。

        for collector in self.collectors:
            try:
                sub = self._process_collector(
                    db, collector, monitoring_kw, region_kw, topic_kw, run_start, batch_id, trigger_type
                )
            except Exception:
                # A failed source has already been recorded by _process_collector;
                # continue so one source cannot abort the scheduled batch.
                logger.exception("采集器 %s 执行异常，继续处理后续数据源", collector.source_name)
                result.failed += 1
                continue
            result.fetched_raw += sub.fetched_raw
            result.created += sub.created
            result.analyzed += sub.analyzed
            result.failed += sub.failed
            result.comments_seen += sub.comments_seen
            result.comments_skipped += sub.comments_skipped
            result.admission_filtered += sub.admission_filtered

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
        region_kw: List[str],
        topic_kw: List[str],
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

        is_weibo_consumer = getattr(collector, "data_source_key", None) == "weibo_octopus"
        duplicate_count = 0
        fetched_raw = 0
        upstream_total = None
        upstream_returned = 0
        try:
            # 向下兼容 keywords= 旧链路；region_kw/topic_kw 驱动地域前置过滤新链路。
            # 采集器依据 region_kw 是否为 None 选择新旧逻辑。
            items = collector.fetch(
                keywords=monitoring_kw, region_kw=region_kw, topic_kw=topic_kw
            ) or []
            # 统计采集器实际抓取并完成基础解析的条数；微博展开评论行会在 Collector 内合并为主帖 item，
            # 因此优先读取采集器暴露的 last_fetched_raw，普通采集器仍回退为 len(items)。
            fetched_raw = int(getattr(collector, "last_fetched_raw", len(items)) or 0)
            upstream_total = getattr(collector, "last_not_exported_total", None)
            upstream_returned = int(
                getattr(collector, "last_not_exported_returned", len(items)) or 0
            )
            comments_seen = int(getattr(collector, "last_comments_seen", 0) or 0)
            comments_skipped = int(getattr(collector, "last_comments_skipped", 0) or 0)
            run.fetched_raw = fetched_raw
            run.upstream_total = upstream_total
            run.upstream_returned = upstream_returned
            run.comments_seen = comments_seen
            run.comments_skipped = comments_skipped

            # 按采集器声明的覆盖范围绑定区域（省/市/县）
            region_resolver = OpinionRegionService()

            # 每条 Opinion 的 AI 分析独立（无共享可变状态），逐采集器新建 Provider。
            # 敏感/风险词由 keywords 表（type='sensitive'）注入；无启用敏感词时
            # get_sensitive_keywords 自动回退内置 DEFAULT_KEYWORDS，风险评分零回归。
            ai = RuleFallbackProvider(keywords=get_sensitive_keywords(db))
            # Phase 2-A：独立风险精炼层（Severity/EventState/ResolutionFlag/final）。
            # 纯函数、不查库；severity 词典经注入，缺省用内置 DEFAULT_SEVERITY_KEYWORDS。
            risk_engine = RiskEngine(severity_keywords=get_severity_keywords(db))
            admission = OpinionAdmissionService()

            c_created = c_analyzed = c_failed = 0
            admission_filtered = 0
            for item in items:
                # 微博评论是公众反馈数据，不是独立舆情主体；Phase 1-A 禁止评论创建 Opinion。
                if item.get("source_type") == "weibo_comment":
                    comments_seen += 1
                    comments_skipped += 1
                    continue
                region_decision = region_resolver.decide(
                    db,
                    item,
                    scope_region_codes=getattr(collector, "scope_region_codes", None),
                )
                admission_result = admission.evaluate(
                    item,
                    region_keywords=region_kw,
                    topic_keywords=topic_kw,
                    collector_name=collector.source_name,
                    source_scope_codes=getattr(collector, "scope_region_codes", None),
                    national_source=region_decision.national_source,
                    region_hits=region_decision.region_hits,
                )
                if not admission_result.accepted or not region_decision.accepted:
                    admission_filtered += 1
                    continue
                admission_reason = dict(admission_result.admission_reason or {})
                admission_reason["region_decision"] = region_decision.as_reason()
                # 1) 去重：已存在则跳过，不重复创建（临界区串行化）
                with self._write_lock:
                    if self._already_exists(db, item):
                        duplicate_count += 1
                        continue

                    # 2) 新建 Opinion（默认 pending，先落库保证失败也保留记录）
                    opinion = Opinion(
                        title=(item.get("title") or "").strip(),
                        content=item.get("content") or "",
                        source=(item.get("source") or "").strip() or collector.source_name,
                        url=(item.get("url") or "").strip(),
                        publish_time=item.get("publish_time"),
                        region_id=region_decision.region_id,
                        risk_score=0,
                        sentiment="neutral",
                        analysis_status="pending",
                        # Phase Weibo-1：社媒扩展字段（既有采集器不传 -> NULL，零回归）
                        source_type=item.get("source_type"),
                        author=(item.get("author") or None),
                        engagement=item.get("engagement"),
                        external_id=(item.get("external_id") or None),
                        relevance_score=admission_result.relevance_score,
                        content_type=admission_result.content_type,
                        admission_reason=admission_reason,
                    )
                    try:
                        db.add(opinion)
                        db.commit()  # 先提交，确保失败记录不丢失
                    except IntegrityError:
                        # P1-2：数据库级唯一约束兜底（并发插入相同 url）。
                        # 视为已存在，跳过，绝不把正常重复冲突当作系统级异常导致整批失败。
                        db.rollback()
                        if self._already_exists(db, item):
                            duplicate_count += 1
                            continue
                        raise  # 非 url 唯一冲突的真实错误，按原样抛出
                c_created += 1

                # 3) AI 分析 + 写回（单条失败隔离；分析写回也在锁内，避免并发更新冲突）
                try:
                    analysis = ai.analyze(
                        f"标题：{opinion.title}\n正文：{opinion.content}"
                    )
                    # Phase 2-A：用 RiskEngine 精炼评分，覆盖 risk_score 并写入新字段。
                    refine = risk_engine.refine(
                        opinion.title, opinion.content, analysis.sentiment
                    )
                    opinion.summary = analysis.summary
                    opinion.sentiment = analysis.sentiment
                    opinion.risk_score = refine.final_risk_score
                    opinion.severity_score = refine.severity_score
                    opinion.event_state = refine.event_state
                    opinion.resolution_flag = refine.resolution_flag
                    # Phase 2-A.1：风险解释字段（仅解释，不参与评分）+ 模型版本。
                    opinion.risk_factors = refine.risk_factors
                    opinion.risk_model_version = RISK_MODEL_VERSION
                    # Phase 2-B.2：风险分类（纯解释性标签，与 risk_factors 同源写入）。
                    opinion.risk_category = refine.risk_category
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
            run.comments_seen = comments_seen
            run.comments_skipped = comments_skipped
            run.admission_filtered = admission_filtered
            run.status = "success" if c_failed == 0 else "partial"
            # 配置异常标注：地域关键词为空 → fail-safe 已拦截全部数据，
            # 在运行记录中显式标记，避免被误读为「普通零数据」。
            if region_kw is not None and not region_kw:
                run.status = "warning"
                run.error_msg = (
                    "配置异常：地域关键词(region_kw)为空，已启用 fail-safe "
                    "拦截无地域数据（非普通零数据，请检查 keywords 表 category='地域' 是否启用）"
                )
            run.end_time = datetime.now(timezone.utc)
            db.commit()

            # 八爪鱼的导出确认必须晚于 Opinion 持久化。普通采集器没有该钩子，
            # 使用可选协议保持 BaseCollector 和其他数据源兼容。
            ack_pending_export = getattr(collector, "ack_pending_export", None)
            can_ack_pending_export = getattr(collector, "can_ack_pending_export", None)
            if callable(ack_pending_export):
                run.ack_status = "pending"
                run.unconfirmed = upstream_returned
                db.commit()

                # Analyzed failures mean the local processing chain is incomplete.
                # Keep the provider queue intact so the batch can be retried.
                if c_failed:
                    run.ack_status = "deferred"
                    run.unconfirmed = upstream_returned
                    run.status = "partial"
                    run.error_msg = (
                        "微博本批分析处理存在失败，已延迟确认；"
                        f"failed={c_failed}"
                    )[:2000]
                    db.commit()
                # The provider ack is task-scoped. Never acknowledge a known
                # partial response; leave it available for a later retry.
                elif callable(can_ack_pending_export) and not can_ack_pending_export():
                    run.ack_status = "deferred"
                    run.unconfirmed = max(
                        0, (upstream_total or upstream_returned) - upstream_returned
                    )
                    run.status = "warning"
                    run.error_msg = (
                        "八爪鱼未导出队列未完整拉取，已延迟确认；"
                        f"total={upstream_total}, returned={upstream_returned}"
                    )[:2000]
                    db.commit()
                else:
                    acknowledged = ack_pending_export()
                    if acknowledged:
                        run.ack_status = "confirmed"
                        run.acknowledged = upstream_returned
                        run.unconfirmed = 0
                    else:
                        run.ack_status = "not_needed"
                        run.unconfirmed = 0
                    db.commit()

            if is_weibo_consumer:
                if run.ack_status == "deferred" and c_failed:
                    ack_reason = "processing_failed"
                elif run.ack_status == "deferred":
                    ack_reason = "partial_queue"
                else:
                    ack_reason = "-"
                logger.info(
                    "Weibo consumer queue: upstream_total=%s upstream_returned=%d "
                    "created=%d duplicate=%d failed=%d ack_status=%s reason=%s",
                    upstream_total,
                    upstream_returned,
                    c_created,
                    duplicate_count,
                    c_failed,
                    run.ack_status,
                    ack_reason,
                )

            return CollectorRunResult(
                collector_type=self.collector_type,
                fetched_raw=fetched_raw,
                created=c_created,
                analyzed=c_analyzed,
                failed=c_failed,
                upstream_total=upstream_total,
                upstream_returned=upstream_returned,
                acknowledged=run.acknowledged,
                unconfirmed=run.unconfirmed,
                ack_status=run.ack_status,
                comments_seen=comments_seen,
                comments_skipped=comments_skipped,
                admission_filtered=admission_filtered,
            )
        except Exception as exc:
            # P1-1：采集器级异常（fetch / 区域解析 / 循环内未捕获异常）必须最终落为 failed，
            # 不得让对应 CollectorRun 永久停留 running；error_msg 保留足够定位信息；
            # 不吞掉异常伪装成功——标记失败后重新抛出，原有调用方行为（异常上抛）不变。
            db.rollback()
            run.status = "failed"
            if run.ack_status == "pending":
                run.ack_status = "failed"
                run.unconfirmed = max(
                    int(run.upstream_returned or 0) - int(run.acknowledged or 0),
                    0,
                )
            run.failed = max(int(run.failed or 0), 1)
            run.error_msg = f"{type(exc).__name__}: {exc}"[:2000]
            run.end_time = datetime.now(timezone.utc)
            try:
                db.add(run)
                db.commit()
            except Exception:
                db.rollback()
            if is_weibo_consumer:
                logger.error(
                    "Weibo consumer queue failed: upstream_total=%s upstream_returned=%d "
                    "created=%d duplicate=%d failed=%d ack_status=%s error=%s",
                    upstream_total,
                    upstream_returned,
                    int(run.created or 0),
                    duplicate_count,
                    int(run.failed or 0),
                    run.ack_status,
                    run.error_msg,
                )
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
        # 与顺序路径一致：扁平 monitoring_kw 向下兼容 + 分组 region_kw/topic_kw 新链路。
        kw_db = session_factory()
        try:
            monitoring_kw = get_monitoring_keywords(kw_db)
            grouped = get_monitoring_keywords_grouped(kw_db)
        finally:
            kw_db.close()
        region_kw: List[str] = grouped.get("地域", [])
        topic_kw: List[str] = grouped.get("主题", [])

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
                return self._process_collector(
                    cdb, collector, monitoring_kw, region_kw, topic_kw, run_start, batch_id, trigger_type
                )
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
                    sub = CollectorRunResult(
                        collector_type=self.collector_type,
                        failed=1,
                    )
                merged.fetched_raw += sub.fetched_raw
                if sub.upstream_total is not None:
                    merged.upstream_total = (merged.upstream_total or 0) + sub.upstream_total
                merged.upstream_returned += sub.upstream_returned
                merged.created += sub.created
                merged.analyzed += sub.analyzed
                merged.failed += sub.failed
                merged.acknowledged += sub.acknowledged
                merged.unconfirmed += sub.unconfirmed
                if sub.ack_status != "not_applicable":
                    merged.ack_status = sub.ack_status
                merged.comments_seen += sub.comments_seen
                merged.comments_skipped += sub.comments_skipped
                merged.admission_filtered += sub.admission_filtered
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
