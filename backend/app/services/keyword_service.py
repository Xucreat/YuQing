"""监测关键词统一服务（单一权威源：keywords 表）。

职责：
  - 作为「采集过滤」与「预警匹配」共用的唯一关键词来源。
  - 从 keywords 表读取全部 word，供采集器与预警服务复用。
  - 带进程内缓存 + 60s TTL：UI 增删关键词后最多 1 分钟内自动生效；
    同时提供显式 clear_monitoring_keywords_cache() 供 CRUD 接口立即失效。
  - 表空时回退 settings.collector_keywords（迁移/应急兜底）。

设计约束：
  - 不依赖具体的采集器或预警实现，保持独立可复用。
  - 仅读取 keywords 表，不写入（写入由 api/keywords.py CRUD 负责）。
"""
from __future__ import annotations

import time
from typing import List, Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.keyword import Keyword

# 进程内缓存（dict 形式保存引用，便于原子替换）
_CACHE: dict = {"words": None, "ts": 0.0}
_TTL_SECONDS: float = 60.0


def get_monitoring_keywords(db: Session) -> List[str]:
    """返回监测关键词列表（来自 keywords 表，作为采集/预警唯一权威源）。

    - 优先返回未过期的缓存；
    - 表非空 → 取全部 word；
    - 表空 → 回退 settings.collector_keywords（保证系统至少有兜底关键词）。
    """
    global _CACHE
    now = time.time()
    if _CACHE["words"] is not None and (now - _CACHE["ts"]) < _TTL_SECONDS:
        return _CACHE["words"]

    rows = db.query(Keyword.word).all()
    words = [r[0].strip() for r in rows if r[0] and r[0].strip()]
    if not words:
        words = [k.strip() for k in settings.collector_keywords.split(",") if k.strip()]

    _CACHE["words"] = words
    _CACHE["ts"] = now
    return words


def clear_monitoring_keywords_cache() -> None:
    """显式失效缓存（关键词 CRUD 后调用，保证立即生效）。"""
    global _CACHE
    _CACHE = {"words": None, "ts": 0.0}
