"""统一关键词词库服务（单一权威源：keywords 表）。

职责：
  - 作为「采集过滤」「预警匹配」「风险评分」共用的唯一关键词来源。
  - 监测关键词（type='monitoring'）驱动采集与预警；
    敏感/风险词（type='sensitive'）驱动风险评分（RuleFallbackProvider）。
  - 两类词均带进程内缓存 + 60s TTL：UI 增删改后最多 1 分钟内自动生效；
    同时提供显式 clear_keyword_cache() 供 CRUD 接口立即失效。
  - 表空时回退 settings.collector_keywords（迁移/应急兜底，仅监测词路径）。

设计约束：
  - 不依赖具体的采集器或预警实现，保持独立可复用。
  - 仅读取 keywords 表，不写入（写入由 api/keywords.py CRUD 负责）。
  - 敏感词读取失败时安全回退到内置 DEFAULT_KEYWORDS，保证风险评分始终可用。
"""
from __future__ import annotations

import json
import time
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.keyword import Keyword
# 内置默认敏感词表：作为「数据库无启用敏感词」时的兜底，保证风险评分零回归。
from app.services.ai.fallback import DEFAULT_KEYWORDS
# 内置默认严重度词表：Phase 2-A RiskEngine 的 severity_weight fallback。
from app.services.risk_engine import DEFAULT_SEVERITY_KEYWORDS

# 进程内缓存（dict 形式保存引用，便于原子替换）
_MON_CACHE: dict = {"words": None, "ts": 0.0}
_SENS_CACHE: dict = {"words": None, "ts": 0.0}
# 分组缓存（与扁平缓存分离，避免互相污染）：{category: [word, ...]}
_MON_GROUPED_CACHE: dict = {"words": None, "ts": 0.0}
# 规则配置缓存（rule_config 非空的关键词，当前仅 id=30「大厂」）
_RULE_CACHE: dict = {"words": None, "ts": 0.0}
_TTL_SECONDS: float = 60.0


def _monitoring_record_count(db: Session) -> int:
    """返回 monitoring 记录总数，用于区分未初始化与全部停用。"""
    return (
        db.query(Keyword.id)
        .filter(Keyword.type == "monitoring")
        .count()
    )


def get_monitoring_keywords(db: Session) -> List[str]:
    """返回监测关键词列表（type='monitoring' 且已启用，作为采集/预警唯一权威源）。

    - 优先返回未过期的缓存；
    - 存在 monitoring 记录 → 只取全部已启用监测词 word，全部停用时返回空列表；
    - 不存在任何 monitoring 记录 → 回退 settings.collector_keywords（初始化/应急兜底）。
    """
    global _MON_CACHE
    now = time.time()
    if _MON_CACHE["words"] is not None and (now - _MON_CACHE["ts"]) < _TTL_SECONDS:
        return _MON_CACHE["words"]

    monitoring_count = _monitoring_record_count(db)
    rows = (
        db.query(Keyword.word)
        .filter(Keyword.type == "monitoring", Keyword.is_enabled == True)  # noqa: E712
        .all()
    )
    words = [r[0].strip() for r in rows if r[0] and r[0].strip()]
    if monitoring_count == 0:
        words = [k.strip() for k in settings.collector_keywords.split(",") if k.strip()]

    _MON_CACHE["words"] = words
    _MON_CACHE["ts"] = now
    return words


def get_monitoring_keywords_grouped(db: Session) -> Dict[str, List[str]]:
    """返回按 ``category`` 分组的监测关键词 ``{category: [word, ...]}``。

    用途：支持「地域前置过滤 + 主题增强」——采集服务按 category 取出
    ``region_kw`` / ``topic_kw`` 分别注入采集器，避免扁平注入时丢失分类信息。

    - 优先返回未过期的缓存；
    - 存在 monitoring 记录时，仅取 ``is_enabled=True`` 的词，按 ``category`` 分组；
    - monitoring 全部停用 → 显式返回 ``{"地域": [], "主题": []}``；
    - 不存在任何 monitoring 记录 → 回退 ``settings.collector_keywords``，整体归入 ``"general"`` 分组；
    - 与 ``get_monitoring_keywords``（扁平列表）互不影响：预警/看板仍用扁平接口。
    """
    global _MON_GROUPED_CACHE
    now = time.time()
    if _MON_GROUPED_CACHE["words"] is not None and (now - _MON_GROUPED_CACHE["ts"]) < _TTL_SECONDS:
        return _MON_GROUPED_CACHE["words"]

    monitoring_count = _monitoring_record_count(db)
    rows = (
        db.query(Keyword.word, Keyword.category)
        .filter(Keyword.type == "monitoring", Keyword.is_enabled == True)  # noqa: E712
        .all()
    )
    grouped: Dict[str, List[str]] = {}
    for word, cat in rows:
        w = (word or "").strip()
        if not w:
            continue
        grouped.setdefault(cat or "general", []).append(w)
    if monitoring_count == 0:
        # 初始化/应急兜底：未初始化的词库不阻塞既有配置链路。
        fallback = [k.strip() for k in settings.collector_keywords.split(",") if k.strip()]
        grouped = {"general": fallback}
    elif not grouped:
        # 管理员明确停用全部 monitoring 词时，不回退 .env。
        grouped = {"地域": [], "主题": []}

    _MON_GROUPED_CACHE["words"] = grouped
    _MON_GROUPED_CACHE["ts"] = now
    return grouped


def get_sensitive_keywords(db: Session) -> List[Tuple[str, int]]:
    """返回已启用的敏感/风险词列表 ``[(word, weight), ...]``（type='sensitive'）。

    用于风险评分（RuleFallbackProvider）。当数据库中没有启用中的敏感词时，
    安全回退到内置 ``DEFAULT_KEYWORDS``，确保风险评分行为与旧版完全一致。
    """
    global _SENS_CACHE
    now = time.time()
    if _SENS_CACHE["words"] is not None and (now - _SENS_CACHE["ts"]) < _TTL_SECONDS:
        return _SENS_CACHE["words"]

    rows = (
        db.query(Keyword.word, Keyword.weight)
        .filter(Keyword.type == "sensitive", Keyword.is_enabled == True)  # noqa: E712
        .all()
    )
    words: List[Tuple[str, int]] = [(r[0], r[1]) for r in rows]
    if not words:
        # 兜底：保持与旧版硬编码 DEFAULT_KEYWORDS 完全一致的风险评分行为。
        words = list(DEFAULT_KEYWORDS)

    _SENS_CACHE["words"] = words
    _SENS_CACHE["ts"] = now
    return words


def get_severity_keywords(db: Session) -> Dict[str, int]:
    """返回严重度词典 ``{harm_word: severity_weight, ...}``（Phase 2-A RiskEngine 用）。

    策略：以内置 ``DEFAULT_SEVERITY_KEYWORDS`` 为底座，再用 keywords 表
    ``type='sensitive'`` 且已启用的 ``severity_weight`` 覆盖（DB 优先），
    保证「无数据库 / 未播种 severity_weight / 测试 / 演示」路径行为确定，
    同时支持业务经 keywords 表标定严重度。

    仅读取 keywords 表，不写入。
    """
    result: Dict[str, int] = dict(DEFAULT_SEVERITY_KEYWORDS)
    try:
        rows = (
            db.query(Keyword.word, Keyword.severity_weight)
            .filter(Keyword.type == "sensitive", Keyword.is_enabled == True)  # noqa: E712
            .all()
        )
    except Exception:
        # severity_weight 列尚未迁移 / 查询异常 → 直接退回内置常量，保证健壮。
        return result
    for word, sw in rows:
        # 仅当 DB 配置了「正严重度权重」时才覆盖默认（severity_weight 为 0/未配置
        # 视为「沿用默认」，避免新列默认值 0 把 DEFAULT_SEVERITY_KEYWORDS 全部清零）。
        if word and sw:
            result[word] = sw
    return result


def clear_keyword_cache() -> None:
    """显式失效全部关键词缓存（关键词 CRUD 后调用，保证立即生效）。"""
    global _MON_CACHE, _SENS_CACHE, _MON_GROUPED_CACHE, _RULE_CACHE
    _MON_CACHE = {"words": None, "ts": 0.0}
    _SENS_CACHE = {"words": None, "ts": 0.0}
    _MON_GROUPED_CACHE = {"words": None, "ts": 0.0}
    _RULE_CACHE = {"words": None, "ts": 0.0}


def get_keyword_rules(db: Session) -> Dict[str, dict]:
    """返回 ``{word: rule_config}``，仅含 ``rule_config`` 非空的 monitoring 关键词。

    当前仅 id=30「大厂」有值；供 ``KeywordFilterService.from_rule_config`` 未来从 DB
    加载规则。运行时仍以 ``keyword_filter_service.DEFAULT_RULE`` 为准（避免迁移 /
    播种时序耦合）；本函数仅作「DB 镜像 → 代码」的可选桥接。

    JSONB 在 SQLAlchemy 下已反序列化为 dict（个别旧 PG 驱动可能返回 str），此处做兜底解析。
    """
    global _RULE_CACHE
    now = time.time()
    if _RULE_CACHE["words"] is not None and (now - _RULE_CACHE["ts"]) < _TTL_SECONDS:
        return _RULE_CACHE["words"]

    rows = (
        db.query(Keyword.word, Keyword.rule_config)
        .filter(Keyword.type == "monitoring", Keyword.rule_config.isnot(None))
        .all()
    )
    rules: Dict[str, dict] = {}
    for word, rc in rows:
        if not rc:
            continue
        if isinstance(rc, str):
            try:
                rc = json.loads(rc)
            except Exception:
                rc = {}
        if isinstance(rc, dict):
            rules[word] = rc

    _RULE_CACHE["words"] = rules
    _RULE_CACHE["ts"] = now
    return rules


# 向后兼容别名（既有调用方可能仍引用此名称）。
def clear_monitoring_keywords_cache() -> None:
    clear_keyword_cache()
