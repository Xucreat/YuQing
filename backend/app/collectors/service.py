"""Collector 采集服务（Phase 3A：采集 → 入库 → 自动 AI 分析闭环）。

职责：
  1. 调度各 Collector.fetch() 拿到标准化 dict 列表。
  2. 按 url 去重（url 为空时退回 title+publish_time 辅助判断），跳过已存在项。
  3. 新建 Opinion（默认 risk_score=0 / sentiment=neutral / analysis_status=pending）。
  4. 调用 AIService.analyze(title, content) 做 AI 分析并写回字段 + 状态流转。
  5. 单条 AI 失败隔离：该条置 analysis_status="failed"（保留数据库记录），
     不影响其余数据；失败计数 failed = created - analyzed。

设计约束（来自用户确认）：
- 复用 AIService.analyze（与手动分析 API 共用分析能力），不抽取公共
  AIAnalysisHelper（MVP 快速验证）；但已在下方标注 TODO Phase 4 待抽取。
- CollectorService 不直接调用 DeepSeek / Provider，统一经 AIService。
- 采集状态存**模块级内存变量**（见 _COLLECTOR_STATUS），重启丢失、不持久化。
  # Phase 3A temporary implementation.
  # Persistent collector task history is postponed.
  # Future: 若增加定时采集，再设计 collector_runs 表。
- 不修改数据库结构 / 不新增迁移 / 不引入 Celery / Redis / 定时任务。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy.orm import Session

from app.collectors.base import BaseCollector
from app.collectors.government_collector import GovernmentCollector
from app.collectors.registry import resolve_collectors
from app.core.config import settings
from app.models.opinion import Opinion
from app.models.region import Region
from app.models.collector_run import CollectorRun
from app.services.ai import AIService

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
            collectors if collectors is not None else resolve_collectors(self.collector_type)
        )
        self.region_id: Optional[int] = region_id

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
    def collect_and_analyze(self, db: Session) -> CollectorRunResult:
        """执行一次采集 + 自动 AI 分析，返回运行结果（Phase 3 表驱动 + 按区域绑定）。

        - 未显式注入 collectors 时，按 db 中的 data_sources 表装配（灰度回退默认源）。
        - 每个采集器独立绑定其 scope_region_codes 对应的 region_id。
        - 5 秒防抖仅对政府网站采集生效。
        """
        global _GOV_LAST_RUN_AT

        # 表驱动装配（优先 data_sources 表，表空回退默认源）；注入模式不覆盖。
        if not self._collectors_injected:
            self.collectors = resolve_collectors(db, self.collector_type)

        # 5 秒防抖（仅政府网站采集）：距上次不足阈值 → 拒绝执行。
        if self._uses_government() and _GOV_LAST_RUN_AT is not None:
            elapsed = (datetime.now(timezone.utc) - _GOV_LAST_RUN_AT).total_seconds()
            if elapsed < THROTTLE_SECONDS:
                raise CollectorThrottled("collector running too frequently")

        result = CollectorRunResult(collector_type=self.collector_type)
        ai = AIService()

        run_start = datetime.now(timezone.utc)
        for collector in self.collectors:
            # 每个采集器独立记录一次采集运行（CollectorRun），用于审计与历史。
            run = CollectorRun(
                collector_name=collector.source_name,
                start_time=run_start,
                status="running",
            )
            db.add(run)
            db.commit()

            items = collector.fetch() or []
            # 统计采集器实际抓取的原始条数（去重前），供前端提示真实抓取量。
            result.fetched_raw += len(items)
            run.fetched_raw = len(items)

            # 按采集器声明的覆盖范围绑定区域（省/市/县）
            region_id = self._resolve_region_id(db, collector)

            c_created = c_analyzed = c_failed = 0
            for item in items:
                # 1) 去重：已存在则跳过，不重复创建
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
                db.add(opinion)
                db.commit()  # 先提交，确保失败记录不丢失
                result.created += 1
                c_created += 1

                # 3) AI 分析 + 写回（单条失败隔离）
                try:
                    analysis = ai.analyze(opinion.title, opinion.content)
                    opinion.summary = analysis.summary
                    opinion.sentiment = analysis.sentiment
                    opinion.risk_score = analysis.risk_score
                    # keywords 在库中为 TEXT 逗号分隔
                    opinion.keywords = ",".join(analysis.keywords)
                    opinion.analysis_suggestion = analysis.suggestion
                    opinion.analysis_status = "completed"
                    opinion.analysis_time = datetime.now(timezone.utc)
                    db.commit()
                    result.analyzed += 1
                    c_analyzed += 1
                except Exception:
                    # 失败：保留该 Opinion 记录，仅状态置 failed
                    db.rollback()
                    opinion.analysis_status = "failed"
                    db.add(opinion)
                    db.commit()
                    c_failed += 1

            # 写回本次采集器运行结果
            run.created = c_created
            run.analyzed = c_analyzed
            run.failed = c_failed
            run.status = "success" if c_failed == 0 else "partial"
            run.end_time = datetime.now(timezone.utc)
            db.commit()

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
