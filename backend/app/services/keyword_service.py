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

import time
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.keyword import Keyword
# 内置默认敏感词表：作为「数据库无启用敏感词」时的兜底，保证风险评分零回归。
from app.services.ai.fallback import DEFAULT_KEYWORDS

# 进程内缓存（dict 形式保存引用，便于原子替换）
_MON_CACHE: dict = {"words": None, "ts": 0.0}
_SENS_CACHE: dict = {"words": None, "ts": 0.0}
_TTL_SECONDS: float = 60.0


def get_monitoring_keywords(db: Session) -> List[str]:
    """返回监测关键词列表（type='monitoring' 且已启用，作为采集/预警唯一权威源）。

    - 优先返回未过期的缓存；
    - 表非空 → 取全部已启用监测词 word；
    - 表空 → 回退 settings.collector_keywords（保证系统至少有兜底关键词）。
    """
    global _MON_CACHE
    now = time.time()
    if _MON_CACHE["words"] is not None and (now - _MON_CACHE["ts"]) < _TTL_SECONDS:
        return _MON_CACHE["words"]

    rows = (
        db.query(Keyword.word)
        .filter(Keyword.type == "monitoring", Keyword.is_enabled == True)  # noqa: E712
        .all()
    )
    words = [r[0].strip() for r in rows if r[0] and r[0].strip()]
    if not words:
        words = [k.strip() for k in settings.collector_keywords.split(",") if k.strip()]

    _MON_CACHE["words"] = words
    _MON_CACHE["ts"] = now
    return words


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


def clear_keyword_cache() -> None:
    """显式失效全部关键词缓存（关键词 CRUD 后调用，保证立即生效）。"""
    global _MON_CACHE, _SENS_CACHE
    _MON_CACHE = {"words": None, "ts": 0.0}
    _SENS_CACHE = {"words": None, "ts": 0.0}


# 向后兼容别名（既有调用方可能仍引用此名称）。
def clear_monitoring_keywords_cache() -> None:
    clear_keyword_cache()
