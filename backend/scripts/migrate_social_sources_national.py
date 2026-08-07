"""Set the formal Weibo and Xiaohongshu sources to national scope.

This is an idempotent data migration for deployments where those rows were
created with an earlier regional default.  Empty ``scope_region_codes`` is the
existing application representation of national coverage.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.collectors.source_config import (
    KEYWORD_SCOPE_ALIASES,
    FILTER_MODES,
    KEYWORD_SCOPES,
    validate_mediacrawler_region_contract,
)
from app.db.session import SessionLocal
from app.models.data_source import DataSource


SOURCE_KEYS = ("weibo_mediacrawler", "xhs_mediacrawler")

# 切换到 national 后仍需校验策略键，但地域关键词不再因为 national 身份被删除。
# collection_mode 负责采集覆盖范围，filter_mode/keyword_scope 负责内容策略。
_REGIONAL_ONLY_STRATEGY_KEYS = ("filter_mode", "keyword_scope")


def _reconcile_national_strategy(key: str, config: dict) -> list[str]:
    """清理非法策略值，保留合法的全国关键词/过滤策略。"""
    dropped: list[str] = []
    allowed = {
        "filter_mode": FILTER_MODES,
        "keyword_scope": KEYWORD_SCOPES,
    }
    for name in _REGIONAL_ONLY_STRATEGY_KEYS:
        value = config.get(name)
        normalized_value = (
            KEYWORD_SCOPE_ALIASES.get(value, value)
            if name == "keyword_scope"
            else value
        )
        if name in config and normalized_value not in allowed[name]:
            dropped.append(f"{key}.{name}={config.pop(name)!r}")
    return dropped


def migrate() -> int:
    changed = 0
    dropped_all: list[str] = []
    with SessionLocal() as db:
        rows = (
            db.query(DataSource)
            .filter(DataSource.key.in_(SOURCE_KEYS))
            .order_by(DataSource.key)
            .all()
        )
        for row in rows:
            config = json.loads(row.config_json or "{}")
            if not isinstance(config, dict):
                raise ValueError(f"{row.key} config_json must be a JSON object")
            config["collection_scope"] = "national"
            config["collection_mode"] = "national"
            dropped_all.extend(_reconcile_national_strategy(row.key, config))
            # 落库前自检：与 registry 装配期、admin API 写入期使用同一道契约校验，
            # 避免迁移脚本成为绕过校验的后门。
            validate_mediacrawler_region_contract(config, None)
            next_config = json.dumps(config, ensure_ascii=False)
            if row.scope_region_codes is not None or row.config_json != next_config:
                row.scope_region_codes = None
                row.config_json = next_config
                changed += 1
        db.commit()
    for item in dropped_all:
        print(f"dropped conflicting key: {item}")
    print(f"updated={changed} found={len(rows)}")
    return changed


if __name__ == "__main__":
    migrate()
