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
from app.collectors.mock_collector import MockCollector
from app.collectors.rss_collector import RSSCollector
from app.collectors.baidu_news_collector import BaiduNewsCollector
from app.collectors.hebei_news_collector import HebeiNewsCollector
from app.collectors.xinhua_collector import XinhuaCollector
from app.collectors.people_collector import PeopleCollector
from app.collectors.chinanews_collector import ChinanewsCollector
from app.collectors.hebei_daily_collector import HebeiDailyCollector
from app.collectors.changcheng_collector import ChangchengCollector
from app.collectors.hebei_gov_collector import HebeiGovCollector
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


def resolve_collectors(collector_type: Optional[str] = None) -> List[BaseCollector]:
    """按采集方式（Pydantic Settings collector_type）解析启用的采集器列表。

    设计（Phase 扩展，先于架构抽象）：
    - mock       -> [MockCollector]（离线演示）
    - government（默认）-> 装配「政府网站 + 所有已启用真实数据源」
      具体由 config 开关驱动：baidu_news_enabled / hebei_news_enabled。
      微博（weibo）已从运行流程移除（维护成本高、稳定性差），仅保留类以兼容。
    其余取值按 government 兜底。
    """
    ctype = (collector_type or settings.collector_type or "government").lower()
    if ctype == "mock":
        return [MockCollector()]

    # government（默认）：政府网站为基，叠加所有已启用的真实数据源。
    collectors: List[BaseCollector] = [GovernmentCollector()]
    if getattr(settings, "baidu_news_enabled", False):
        collectors.append(BaiduNewsCollector())
    if getattr(settings, "hebei_news_enabled", False):
        collectors.append(HebeiNewsCollector())
    # Phase 2 新增国家级 / 省级数据源（开关驱动，默认开启）。
    if getattr(settings, "xinhua_enabled", False):
        collectors.append(XinhuaCollector())
    if getattr(settings, "people_enabled", False):
        collectors.append(PeopleCollector())
    if getattr(settings, "chinanews_enabled", False):
        collectors.append(ChinanewsCollector())
    if getattr(settings, "hebei_daily_enabled", False):
        collectors.append(HebeiDailyCollector())
    if getattr(settings, "changcheng_enabled", False):
        collectors.append(ChangchengCollector())
    if getattr(settings, "hebei_gov_enabled", False):
        collectors.append(HebeiGovCollector())
    # 微博：已从运行流程移除，不再装配（保留 WeiboCollector 类以兼容）。
    return collectors


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
    def _resolve_region_id(self, db: Session) -> int:
        """解析绑定区域：优先使用显式 region_id；否则用种子区域 131028（大厂县）。"""
        if self.region_id is not None:
            region = db.get(Region, self.region_id)
            if region is None:
                raise RuntimeError(
                    f"Collector region_id={self.region_id} 不存在，请检查区域配置。"
                )
            return self.region_id

        # 默认：种子区域 大厂回族自治县（code=131028）
        region = db.query(Region).filter(Region.code == "131028").first()
        if region is None:
            # 兜底：取任意首个区域（避免种子缺失时整体失败）
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
        """执行一次采集 + 自动 AI 分析，返回运行结果。

        Phase 3B：涉及政府网站时启用 5 秒防抖——距上次政府采集不足
        THROTTLE_SECONDS 秒则抛 CollectorThrottled（API 层转 429），
        避免误操作连续请求政府网站。
        """
        global _GOV_LAST_RUN_AT

        # 5 秒防抖（仅政府网站采集）：距上次不足阈值 → 拒绝执行。
        if self._uses_government() and _GOV_LAST_RUN_AT is not None:
            elapsed = (datetime.now(timezone.utc) - _GOV_LAST_RUN_AT).total_seconds()
            if elapsed < THROTTLE_SECONDS:
                raise CollectorThrottled("collector running too frequently")

        region_id = self._resolve_region_id(db)
        result = CollectorRunResult(collector_type=self.collector_type)
        ai = AIService()

        run_start = datetime.now(timezone.utc)
        for collector in self.collectors:
            # 每个采集器独立记录一次采集运行（CollectorRun），用于审计与历史。
            # 此前该表已建但从不写入，/sources/history 恒为空；现补上真实写入。
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
