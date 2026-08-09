"""数据源管理后台 API（admin）。

提供 data_sources 表的只读列表 + 部分字段更新，以及按源查询采集历史。
- GET    /admin/data-sources           列表 + 筛选(区域/启用/关键字) + 分页
- PATCH  /admin/data-sources/{id}      更新 enabled / priority / config_json
- GET    /admin/data-sources/{id}/runs 复用 collector_runs（按 collector_name == ds.name）

设计说明：
- 不新增数据库迁移；DataSource 模型已含所需字段。
- 列表的"最近运行状态/时间"由 collector_runs 按 collector_name 关联最新一条计算
  （collector_name 与 DataSource.name 在当前种子数据下一致；PATCH 不改名，安全）。
- 区域显示：scope_region_codes(CSV) -> Region 表 name；空=全国。
- 启停/调优先级后，POST /api/collector/run 经 resolve_collectors 实时读取生效（无需额外代码）。
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, or_, select, case, String, text
from sqlalchemy.orm import Session

from app.collectors.generic_site import GenericSiteCollector
from app.collectors.mediacrawler_platform import (
    MEDIACRAWLER_CONFIG_KEYS,
    is_mediacrawler_collector,
)
from app.collectors.mediacrawler_runtime import MediaCrawlerRuntimeFactory
from app.collectors.registry import import_class
from app.collectors.source_config import STRATEGY_KEYS
from app.collectors.source_config import (
    COLLECTION_MODES,
    COLLECTOR_DEFAULT_STRATEGY,
    DEFAULT_COLLECTION_MODE,
    FILTER_MODES,
    KEYWORD_SCOPES,
    NON_FILTER_STRATEGY_CLASS_PATHS,
    DataSourceConfig,
    validate_mediacrawler_region_contract,
    validate_data_source_config,
    _validate_legacy_collection_config,
)
from app.core.config import settings
from app.core.dependencies import get_current_user
from app.core.permissions import require_admin, require_permission
from app.db.session import get_db
from app.models.collector_run import CollectorRun
from app.models.data_source import DataSource
from app.models.region import Region
from app.models.user import User
from app.services.audit_service import audit_write
from app.services.keyword_service import get_monitoring_keywords_grouped
from app.services.data_source_health import DataSourceHealthSummaryService
from app.services.region_catalog import (
    region_catalog_items,
    region_catalog_map,
    sync_region_codes,
)
from app.schemas.region import RegionCatalogItemOut

logger = logging.getLogger(__name__)

# 全国省级行政区（GB/T 2260 6 位 adcode），用于新建采集源时下拉选择「全国区域」。
# 与已有 Hebei 区域（DB regions 表 + 已用 scope_region_codes）合并，向后兼容。
CHINA_REGIONS: dict[str, str] = {
    "110000": "北京市",
    "120000": "天津市",
    "130000": "河北省",
    "140000": "山西省",
    "150000": "内蒙古自治区",
    "210000": "辽宁省",
    "220000": "吉林省",
    "230000": "黑龙江省",
    "310000": "上海市",
    "320000": "江苏省",
    "330000": "浙江省",
    "340000": "安徽省",
    "350000": "福建省",
    "360000": "江西省",
    "370000": "山东省",
    "410000": "河南省",
    "420000": "湖北省",
    "430000": "湖南省",
    "440000": "广东省",
    "450000": "广西壮族自治区",
    "460000": "海南省",
    "500000": "重庆市",
    "510000": "四川省",
    "520000": "贵州省",
    "530000": "云南省",
    "540000": "西藏自治区",
    "610000": "陕西省",
    "620000": "甘肃省",
    "630000": "青海省",
    "640000": "宁夏回族自治区",
    "650000": "新疆维吾尔自治区",
    "710000": "中国台湾",
    "810000": "中国香港",
    "820000": "中国澳门",
}

admin_ds_router = APIRouter(
    prefix="/admin/data-sources",
    tags=["admin-data-sources"],
    dependencies=[Depends(get_current_user)],
)

# 用户可自助添加的数据源类型 -> 采集器类（均为 config 驱动，无需写代码）。
# 真实抓取校验由 GenericSiteCollector.test_fetch 完成。
_TYPE_CLASS_PATH: dict = {
    "generic_site": "app.collectors.generic_site.GenericSiteCollector",
    "news_site": "app.collectors.generic_site.GenericSiteCollector",
    "gov_site": "app.collectors.generic_site.GenericSiteCollector",
    "search": "app.collectors.generic_site.GenericSiteCollector",
    "rss": "app.collectors.generic_site.GenericSiteCollector",
    "foreign_rss": "app.collectors.foreign_rss.ForeignRSSCollector",
    "social": (
        "app.collectors.media_crawler_platform_collector."
        "MediaCrawlerPlatformCollector"
    ),
}

# —— 专用型 / 通用型 采集器区分与 config_json 校验（Phase 3 优化）——
# 专用型采集器（GovernmentCollector / XinhuaCollector 等）的 urls / keywords
# 等逻辑写在类内部，config_json 必须为空（{}）；通用型（GenericSiteCollector）
# 依赖 config_json 驱动，需校验其支持的字段。
GENERIC_CLASS_PATH = "app.collectors.generic_site.GenericSiteCollector"
MEDIACRAWLER_CLASS_PATH = (
    "app.collectors.media_crawler_weibo_collector.MediaCrawlerWeiboCollector"
)
MEDIACRAWLER_PLATFORM_CLASS_PATH = (
    "app.collectors.media_crawler_platform_collector.MediaCrawlerPlatformCollector"
)
MEDIACRAWLER_ALLOWED_KEYS = set(MEDIACRAWLER_CONFIG_KEYS)

# GenericSiteCollector 实际支持的 config_json 顶层字段（含继承 BaseHttpCollector）。
GENERIC_ALLOWED_KEYS = {
    "source_name", "list_urls", "link_rule", "content_selectors",
    "keywords", "max_articles", "max_items", "filter_mode", "keyword_scope",
    "request_interval", "timeout",
    "max_retries", "retry_backoff",
    # Phase DataSource-National-Mode-3：允许显式声明采集模式（regional/national）。
    "collection_mode",
}

# 专用型采集器允许的「非数据」配置键：策略键 + 采集模式声明。
# 专用型（xinhua/people/chinanews/baidu 等 national-scope 源）可借此声明 collection_mode，
# 其余业务键仍禁止（保持专用型约束）。
DEDICATED_ALLOWED_KEYS = set(STRATEGY_KEYS) | {"collection_mode"}
# link_rule 子字段白名单。
GENERIC_LINK_RULE_KEYS = {
    "href_contains", "href_regex", "href_exclude", "title_blacklist", "max_links",
}

DEDICATED_EMPTY_HINT = "当前采集器为专用型采集器，无需填写自定义配置。请保持配置为空（{}）。"

_FULL_COLLECTION_CLASS_PATHS = {
    "app.collectors.government_collector.GovernmentCollector",
}
_GLOBAL_REGION_CLASS_PATHS = {
    "app.collectors.baidu_news_collector.BaiduNewsCollector",
    "app.collectors.xinhua_collector.XinhuaCollector",
    "app.collectors.people_collector.PeopleCollector",
    "app.collectors.chinanews_collector.ChinanewsCollector",
}


def _is_config_empty(raw, extra_allow: set = set()) -> bool:
    """判定 config_json 是否为「空配置」（专用型采集器允许的唯一状态）。

    与现有存储约定一致：None / 空字符串 / '{}' / {} 均视为空；
    非法 JSON 不视为「空」，交由后续校验报错。

    ``extra_allow``：除 ``STRATEGY_KEYS`` 外，额外被计入「非数据键」的键（如
    ``collection_mode``）——这些键存在不改变「空配置」判定，使专用型源可声明采集模式。
    """
    allow = set(STRATEGY_KEYS) | set(extra_allow)
    if raw is None:
        return True
    if isinstance(raw, str):
        s = raw.strip()
        if s == "":
            return True
        try:
            parsed = json.loads(s)
        except json.JSONDecodeError:
            return False
        return isinstance(parsed, dict) and len({k: v for k, v in parsed.items() if k not in allow}) == 0
    if isinstance(raw, dict):
        eff = {k: v for k, v in raw.items() if k not in allow}
        return len(eff) == 0
    return False


def _validate_collection_config(cfg: dict) -> str | None:
    """校验 collection_mode 语义组合（National-Mode-3）。返回错误字符串；无错误返回 None。

    明确拒绝矛盾组合（如 national + region_only），不静默修正。

    注意：本函数仅做「采集模式语义组合」校验，复用于通用型与专用型源。
    不能调用 ``validate_data_source_config``（MediaCrawler 专属校验器），
    否则会把通用型 config_json 里的 source_name/list_urls/link_rule/
    content_selectors/max_articles/timeout 等合法键误判成「MediaCrawler 不支持的
    顶级键」而整体拒绝。MediaCrawler 源走独立的 ``_validate_mediacrawler_config``，
    不经过本函数。
    """
    try:
        _validate_legacy_collection_config(cfg)
    except ValueError as e:
        return str(e)
    return None


def _is_generic(class_path: str) -> bool:
    return (class_path or "") == GENERIC_CLASS_PATH


def _is_foreign(class_path: str) -> bool:
    return "foreign_rss" in (class_path or "")


def _has_foreign_config(raw: str | None) -> bool:
    cfg, err = _parse_config_json(raw or "{}")
    return not err and isinstance(cfg, dict) and cfg.get("is_foreign") is True


def _is_foreign_source(ds: DataSource) -> bool:
    return _is_foreign(ds.class_path) or _has_foreign_config(ds.config_json)


FOREIGN_ALLOWED_KEYS = {
    "is_foreign", "collector", "source_name", "feeds", "proxy_env", "enabled",
    "schedule_enabled", "keywords", "collection_mode", "collection_scope",
    "filter_mode", "keyword_scope", "max_items", "timeout", "max_content_length",
    "request_interval", "max_retries", "fetch_full_text", "connect_timeout",
    "read_timeout", "language",
    "respect_robots",
}


def _validate_foreign_config(cfg: dict) -> str | None:
    if not isinstance(cfg, dict):
        return "foreign config_json must be a JSON object"
    if cfg.get("is_foreign") is not True:
        return "foreign data source requires config_json.is_foreign=true"
    feeds = cfg.get("feeds")
    if not isinstance(feeds, list) or not any(str(v).strip() for v in feeds):
        return "foreign data source requires at least one RSS feed"
    if any(
        not isinstance(v, str) or not v.strip().lower().startswith(("http://", "https://"))
        for v in feeds
        if str(v).strip()
    ):
        return "foreign RSS feeds must use http:// or https:// URLs"
    keywords = cfg.get("keywords")
    if not isinstance(keywords, list) or not any(str(v).strip() for v in keywords):
        return "foreign data source requires at least one keyword"
    unknown = sorted(set(cfg) - FOREIGN_ALLOWED_KEYS)
    if unknown:
        return f"foreign config_json contains unsupported keys: {', '.join(unknown)}"
    proxy_env = cfg.get("proxy_env")
    if proxy_env is not None and (
        not isinstance(proxy_env, str)
        or not proxy_env
        or not proxy_env[0].isalpha()
        or not proxy_env.replace("_", "").isalnum()
        or proxy_env.upper() != proxy_env
    ):
        return "proxy_env must be an environment variable name"
    if cfg.get("collection_mode") not in (None, "foreign"):
        return "foreign data source cannot use domestic collection_mode"
    if cfg.get("collection_scope") not in (None, "foreign"):
        return "foreign data source cannot use domestic collection_scope"
    return None


def _is_mediacrawler(class_path: str) -> bool:
    try:
        return is_mediacrawler_collector(import_class(class_path))
    except (ImportError, AttributeError, ValueError):
        return (class_path or "") == MEDIACRAWLER_CLASS_PATH


def _validate_mediacrawler_config(
    cfg: dict, scope_region_codes: str | None = None
) -> str | None:
    unknown = sorted(set(cfg) - MEDIACRAWLER_ALLOWED_KEYS)
    if unknown:
        return f"MediaCrawler config contains unsupported keys: {', '.join(unknown)}"
    try:
        validate_mediacrawler_region_contract(cfg, scope_region_codes)
    except ValueError as exc:
        return str(exc)
    return None


def _validate_generic_config(cfg: dict) -> str | None:
    """校验通用型 config_json 字段。返回首个错误；无错误返回 None。

    发现未知字段明确报错，不静默忽略（避免「用户以为配置生效，实则无效」）。
    """
    if not isinstance(cfg, dict) or not cfg:
        return "通用型采集器必须提供 config_json（至少包含 list_urls）"
    unknown = [k for k in cfg if k not in GENERIC_ALLOWED_KEYS]
    if unknown:
        return (
            f"config_json 包含不支持的字段：{', '.join(unknown)}"
            f"（通用型采集器仅支持：{', '.join(sorted(GENERIC_ALLOWED_KEYS))}）"
        )
    if isinstance(cfg.get("link_rule"), dict):
        bad = [k for k in cfg["link_rule"] if k not in GENERIC_LINK_RULE_KEYS]
        if bad:
            return f"link_rule 包含不支持的子字段：{', '.join(bad)}"
    return None


def _region_map(db: Session) -> dict:
    # 以全国省级行政区为基底，DB regions 表（如河北省/市/县）覆盖同名项，保证
    # 新建源选了全国省份时列表也能正确显示名称（而非回退成 code）。
    m = dict(CHINA_REGIONS)
    m.update(region_catalog_map())
    for code, name in db.execute(select(Region.code, Region.name)).all():
        m[code] = name
    return m


def _scope_to_codes(value: str | list[str] | tuple[str, ...] | None) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [c.strip() for c in value.split(",") if c.strip()]
    if isinstance(value, (list, tuple)):
        return [str(c).strip() for c in value if str(c).strip()]
    raise ValueError("scope_region_codes must be a comma-separated string or list")


def _validated_scope_codes(value) -> list[str]:
    try:
        codes = _scope_to_codes(value)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    catalog_codes = {item["code"] for item in region_catalog_items()}
    unknown = [code for code in codes if code not in catalog_codes]
    if unknown:
        raise HTTPException(
            status_code=422,
            detail=f"unknown region codes: {', '.join(unknown)}",
        )
    return list(dict.fromkeys(codes))


def _align_mediacrawler_collection_mode(
    ds: DataSource, config: dict, scope_codes: list[str] | None = None
) -> dict:
    if not _is_mediacrawler(ds.class_path):
        return config
    codes = (
        _scope_to_codes(ds.scope_region_codes)
        if scope_codes is None
        else scope_codes
    )
    mode = "regional" if codes else "national"
    config["collection_scope"] = mode
    config["collection_mode"] = mode
    return config


def _split_source_keywords(raw: Any) -> list[str] | None:
    """镜像 GenericSiteCollector 对字符串/列表关键词的解析，仅用于只读解释。"""
    if isinstance(raw, str):
        return [word.strip() for word in raw.split(",") if word and word.strip()]
    if isinstance(raw, list):
        return [str(word).strip() for word in raw if str(word).strip()]
    return None


def _generic_keyword_strategy(raw_config: Any, region_keywords: list[str]) -> dict:
    try:
        if raw_config is None or (isinstance(raw_config, str) and not raw_config.strip()):
            config: dict = {}
        elif isinstance(raw_config, str):
            config = json.loads(raw_config)
        elif isinstance(raw_config, dict):
            config = raw_config
        else:
            raise ValueError("config_json 格式不支持")
        if not isinstance(config, dict):
            raise ValueError("config_json 不是对象")
    except (TypeError, ValueError, json.JSONDecodeError):
        return {
            "keyword_mode": "unknown",
            "keyword_source": "无法判定",
            "effective_keywords": [],
            "keyword_description": "数据源关键词配置无法解析",
        }

    if "keywords" not in config:
        return {
            "keyword_mode": "global_region",
            "keyword_source": "关键词管理-地域分类",
            "effective_keywords": list(region_keywords),
            "keyword_description": "使用全局启用地域词进行过滤",
        }

    source_keywords = _split_source_keywords(config["keywords"])
    if source_keywords is None:
        return {
            "keyword_mode": "unknown",
            "keyword_source": "无法判定",
            "effective_keywords": [],
            "keyword_description": "数据源 keywords 配置格式不支持",
        }
    if not source_keywords:
        return {
            "keyword_mode": "no_filter",
            "keyword_source": "数据源配置-config_json.keywords",
            "effective_keywords": [],
            "keyword_description": "未配置有效关键词，全量放行",
        }
    return {
        "keyword_mode": "source_keywords",
        "keyword_source": "数据源配置-config_json.keywords",
        "effective_keywords": source_keywords,
        "keyword_description": "使用数据源独立关键词进行过滤",
    }


def _keyword_strategy(ds: DataSource, region_keywords: list[str]) -> dict:
    if _is_foreign(ds.class_path):
        cfg, err = _parse_config_json(ds.config_json)
        words = cfg.get("keywords", []) if not err and isinstance(cfg, dict) else []
        if isinstance(words, str):
            words = [word.strip() for word in words.split(",") if word.strip()]
        return {
            "keyword_mode": "foreign_keywords",
            "keyword_source": "外网关键词库",
            "effective_keywords": [str(word).strip() for word in (words or []) if str(word).strip()],
            "keyword_description": "仅使用 foreign_keywords，不读取国内关键词",
        }
    if _is_generic(ds.class_path):
        return _generic_keyword_strategy(ds.config_json, region_keywords)
    if ds.class_path in _FULL_COLLECTION_CLASS_PATHS:
        return {
            "keyword_mode": "full_collection",
            "keyword_source": "采集器固定策略",
            "effective_keywords": [],
            "keyword_description": "全量采集，不受关键词管理影响",
        }
    if ds.class_path in _GLOBAL_REGION_CLASS_PATHS:
        return {
            "keyword_mode": "global_region",
            "keyword_source": "关键词管理-地域分类",
            "effective_keywords": list(region_keywords),
            "keyword_description": "使用全局启用地域词进行过滤",
        }
    return {
        "keyword_mode": "unknown",
        "keyword_source": "无法判定",
        "effective_keywords": [],
        "keyword_description": "当前专用采集器的关键词策略未纳入解释映射",
    }


def _enabled_region_keywords(db: Session) -> list[str]:
    """读取当前有效地域词；解释失败不得影响原数据源列表接口。"""
    try:
        grouped = get_monitoring_keywords_grouped(db)
        return list(grouped.get("地域", []))
    except Exception:  # noqa: BLE001 - 解释字段必须降级而非中断原接口
        logger.exception("读取数据源关键词策略的全局地域词失败")
        return []


def _effective_filter_strategy(ds: DataSource) -> dict:
    """只读解析某数据源「实际生效过滤策略」（Phase DataSource-Filter-Config-4）。

    复用 source_config.DataSourceConfig.effective_filter_strategy，并据采集器类型
    回退到其历史默认；不应用本策略的采集器标记为 not_applicable。
    """
    raw = ds.config_json
    if raw is None or (isinstance(raw, str) and raw.strip() in ("", "{}")):
        cfg: dict = {}
    elif isinstance(raw, str):
        try:
            cfg = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            cfg = {}
    elif isinstance(raw, dict):
        cfg = raw
    else:
        cfg = {}
    if not isinstance(cfg, dict):
        cfg = {}

    if _is_foreign(ds.class_path):
        return {
            "configured_filter_mode": None,
            "configured_keyword_scope": None,
            "effective_filter_mode": "foreign_or",
            "effective_keyword_scope": "foreign_keywords",
            "source": "foreign_pipeline",
        }
    if ds.class_path in NON_FILTER_STRATEGY_CLASS_PATHS:
        dcfg = DataSourceConfig(cfg, source_key=ds.key)
        return {
            "configured_filter_mode": dcfg.get_str("filter_mode", None, allowed=FILTER_MODES),
            "configured_keyword_scope": dcfg.get_str("keyword_scope", None, allowed=KEYWORD_SCOPES),
            "effective_filter_mode": None,
            "effective_keyword_scope": None,
            "source": "not_applicable",
        }

    defaults = COLLECTOR_DEFAULT_STRATEGY.get(ds.class_path, ("region_only", None))
    return DataSourceConfig(cfg, source_key=ds.key).effective_filter_strategy(
        default_filter_mode=defaults[0],
        default_keyword_scope=defaults[1],
    )


def _serialize(
    ds: DataSource,
    region_map: dict,
    latest: dict | None = None,
    *,
    region_keywords: list[str] | None = None,
    runs_by_name: dict[str, list[CollectorRun]] | None = None,
) -> dict:
    codes = _scope_to_codes(ds.scope_region_codes)
    names = [region_map.get(c, c) for c in codes]
    run = latest.get(ds.name) if latest else None
    strategy = _keyword_strategy(ds, region_keywords or [])
    health_summary = DataSourceHealthSummaryService().summarize(
        ds, (runs_by_name or {}).get(ds.name, [])
    )
    return {
        "id": ds.id,
        "key": ds.key,
        "name": ds.name,
        "type": ds.type,
        "enabled": ds.enabled,
        "priority": ds.priority,
        "scope_region_codes": ds.scope_region_codes,
        "region_codes": codes,
        "region_names": names,
        "scope_display": "外网" if _is_foreign(ds.class_path) else ("全国" if not codes else "、".join(names)),
        "config_json": ds.config_json,
        "collector_kind": "foreign" if _is_foreign(ds.class_path) else ("generic" if _is_generic(ds.class_path) else "dedicated"),
        # 缓存列（当前未被采集流程写回，可能为空）
        "last_run_at": ds.last_run_at.isoformat() if ds.last_run_at else None,
        "last_status": ds.last_status,
        # 由 collector_runs 计算得到的最近运行状态/时间（权威）
        "latest_run_status": run.status if run else None,
        "latest_run_at": run.start_time.isoformat() if run and run.start_time else None,
        "updated_at": ds.updated_at.isoformat() if ds.updated_at else None,
        "health_summary": health_summary,
        # Phase DataSource-Schedule-1：调度频率字段
        "schedule_enabled": ds.schedule_enabled,
        "schedule_interval_minutes": ds.schedule_interval_minutes,
        "next_collect_time": ds.next_collect_time.isoformat() if ds.next_collect_time else None,
        "last_collect_time": ds.last_collect_time.isoformat() if ds.last_collect_time else None,
        **strategy,
        # Phase DataSource-Filter-Config-4：实际生效过滤策略透明化（只读解析，不改采集）
        "effective_filter_strategy": _effective_filter_strategy(ds),
    }


def _parse_config_json(raw) -> tuple:
    """解析 config_json（字符串或对象）。返回 (dict, error_str)。"""
    if raw is None:
        return None, "config_json 不能为空"
    if isinstance(raw, dict):
        return raw, None
    if isinstance(raw, str):
        if not raw.strip():
            return None, "config_json 不能为空"
        try:
            cfg = json.loads(raw)
        except json.JSONDecodeError as e:
            return None, f"config_json 不是合法 JSON：{e}"
        if not isinstance(cfg, dict):
            return None, "config_json 必须是 JSON 对象"
        return cfg, None
    return None, "config_json 格式不支持"


def _build_test(
    class_path: str,
    config: dict,
    *,
    data_source_key: str | None = None,
) -> dict:
    """构建采集器并做一次轻量真实抓取校验。返回 {ok, error, verified, ...}。"""
    if _is_foreign(class_path):
        # Foreign sources are intentionally kept in a dry-run/gray-rollout state.
        # Creating or editing one must never make a live network request.
        return {
            "ok": True,
            "verified": False,
            "network_test_skipped": True,
            "note": "外网数据源跳过实时网络校验，仅执行结构校验",
        }
    # 策略键（max_items/filter_mode/keyword_scope）不是构造函数参数，装配时由
    # registry 剥离后注入 source_config；此处若函数拿到的是完整 config_json，
    # 需同样剥离，否则专用型采集器会因未知关键字参数 TypeError。
    build_cfg = {k: v for k, v in (config or {}).items() if k not in STRATEGY_KEYS}
    try:
        cls = import_class(class_path)
        if is_mediacrawler_collector(cls):
            from app.collectors.mediacrawler_platform import get_mediacrawler_platform_spec

            platform_spec = get_mediacrawler_platform_spec(
                (config or {}).get("platform")
            )
            declared_spec = getattr(cls, "platform_spec", None)
            if (
                declared_spec is not None
                and declared_spec.platform != platform_spec.platform
            ):
                return {
                    "ok": False,
                    "verified": False,
                    "error": (
                        "MediaCrawler class_path 与 config_json.platform 不匹配："
                        f"{declared_spec.platform} != {platform_spec.platform}"
                    ),
                }
            collector = cls(
                **build_cfg,
                platform_spec=platform_spec,
                data_source_key=data_source_key
                or f"admin_validation_{platform_spec.platform}",
                runtime_factory=MediaCrawlerRuntimeFactory(
                    source_key=data_source_key
                    or f"admin_validation_{platform_spec.platform}",
                    platform_spec=platform_spec,
                ),
            )
            return {
                "ok": True,
                "verified": False,
                "note": (
                    "MediaCrawler source contract validated without starting "
                    "a real subprocess"
                ),
                "platform": platform_spec.platform,
            }
        collector = cls(**build_cfg)
    except Exception as exc:
        return {
            "ok": False,
            "verified": False,
            "error": f"采集器构建失败（{class_path}）：{type(exc).__name__}: {exc}",
        }
    if isinstance(collector, GenericSiteCollector):
        res = collector.test_fetch()
        res["verified"] = True
        return res
    # 非通用采集器（bespoke）：尽力而为的单项种子校验，否则仅结构校验通过
    seed = getattr(collector, "list_urls", None) or getattr(collector, "seed_urls", None)
    if isinstance(seed, (list, tuple)) and seed:
        html = collector._get(seed[0])
        if html:
            return {"ok": True, "verified": False, "note": "非通用采集器：首个种子 URL 可访问", "list_url": seed[0]}
        return {"ok": False, "verified": False, "error": f"种子 URL 无法抓取：{seed[0]}"}
    return {"ok": True, "verified": False, "note": "非通用采集器，跳过实时抓取校验（仅结构校验通过）"}


def _validate_create(body) -> str | None:
    """返回首个校验错误字符串；通过返回 None。"""
    if not isinstance(body, dict):
        return "请求体必须是 JSON 对象"
    name = (body.get("name") or "").strip()
    if not name:
        return "名称（name）不能为空"
    key = (body.get("key") or "").strip()
    if not key:
        return "标识（key）不能为空"
    if " " in key or not key.replace("_", "").isalnum():
        return "key 只能包含字母、数字、下划线，且不能有空格"
    if body.get("priority") is not None:
        try:
            int(body["priority"])
        except (TypeError, ValueError):
            return "priority 必须为整数"
    if body.get("enabled") is not None and not isinstance(body.get("enabled"), bool):
        return "enabled 必须为布尔值"
    if body.get("schedule_enabled") is not None and not isinstance(
        body.get("schedule_enabled"), bool
    ):
        return "schedule_enabled 必须为布尔值"
    if body.get("schedule_interval_minutes") is not None:
        try:
            interval = int(body["schedule_interval_minutes"])
        except (TypeError, ValueError):
            return "schedule_interval_minutes 必须为整数"
        if interval < 5:
            return "schedule_interval_minutes 必须大于等于 5"
    # —— 配置校验：专用型禁止非空；通用型校验字段 ——
    raw_cfg = body.get("config_json")
    class_path = body.get("class_path") or _TYPE_CLASS_PATH.get(
        (body.get("type") or "generic_site"), GENERIC_CLASS_PATH
    )
    if _is_foreign(class_path):
        if _scope_to_codes(body.get("scope_region_codes")):
            return "foreign data source must not use region scope"
        cfg, err = _parse_config_json(raw_cfg)
        if err:
            return err
        return _validate_foreign_config(cfg)
    if _is_mediacrawler(class_path):
        cfg, err = _parse_config_json(raw_cfg)
        if err:
            return err
        return _validate_mediacrawler_config(cfg, body.get("scope_region_codes"))
    if _is_generic(class_path):
        if _is_config_empty(raw_cfg):
            return "通用型采集器必须提供 config_json（至少包含 list_urls）"
        cfg, err = _parse_config_json(raw_cfg)
        if err:
            return err
        gerr = _validate_generic_config(cfg)
        if gerr:
            return gerr
        # National-Mode-3：collection_mode 组合校验
        return _validate_collection_config(cfg)
    else:
        # 专用型：仅允许空配置 或 仅含策略键 / collection_mode
        if not _is_config_empty(raw_cfg, extra_allow={"collection_mode"}):
            return DEDICATED_EMPTY_HINT
        # 非空（含策略键/collection_mode）时仍需校验组合
        if raw_cfg:
            cfg, err = _parse_config_json(raw_cfg)
            if err:
                return err
            cerr = _validate_collection_config(cfg)
            if cerr:
                return cerr
        return None


@admin_ds_router.get("")
def list_data_sources(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    q: str | None = None,
    enabled: bool | None = None,
    region_code: str | None = None,
    is_foreign: bool | None = Query(None, description="按 config_json.is_foreign 过滤"),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("sources:read")),
):
    region_map = _region_map(db)

    stmt = select(DataSource)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(DataSource.name.like(like), DataSource.key.like(like)))
    if enabled is not None:
        stmt = stmt.where(DataSource.enabled == enabled)
    if region_code:  # 具体区域：命中该 code 或全国(空)源
        stmt = stmt.where(
            or_(
                DataSource.scope_region_codes.like(f"%{region_code}%"),
                DataSource.scope_region_codes.is_(None),
                DataSource.scope_region_codes == "",
            )
        )

    offset = (page - 1) * size
    if is_foreign is None:
        total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        rows = db.scalars(
            stmt.order_by(DataSource.priority.asc(), DataSource.id.asc())
            .offset(offset)
            .limit(size)
        ).all()
    else:
        candidates = db.scalars(
            stmt.order_by(DataSource.priority.asc(), DataSource.id.asc())
        ).all()
        filtered = [
            row
            for row in candidates
            if _is_foreign_source(row) is bool(is_foreign)
        ]
        total = len(filtered)
        rows = filtered[offset: offset + size]

    # 最近运行：按 collector_name 聚合最新一条
    names = [r.name for r in rows]
    latest: dict = {}
    runs_by_name: dict[str, list[CollectorRun]] = {name: [] for name in names}
    if names:
        foreign_names = {row.name for row in rows if _is_foreign(row.class_path)}
        run_scope_filter = or_(
            *[
                (CollectorRun.collector_name == name)
                & (
                    CollectorRun.scope == ("foreign" if name in foreign_names else "domestic")
                )
                for name in names
            ]
        )
        runs = db.scalars(
            select(CollectorRun)
            .where(run_scope_filter)
            .order_by(CollectorRun.start_time.desc())
        ).all()
        for r in runs:
            latest.setdefault(r.collector_name, r)
            runs_by_name.setdefault(r.collector_name, []).append(r)

    region_keywords = _enabled_region_keywords(db)
    items = [
        _serialize(
            r,
            region_map,
            latest,
            region_keywords=region_keywords,
            runs_by_name=runs_by_name,
        )
        for r in rows
    ]

    # 区域筛选项：在「已使用 code」基础上补全全国省级行政区，
    # 使新建采集源弹窗的下拉菜单可选全国任意省份（不再仅限河北相关区域）。
    all_codes = set(CHINA_REGIONS.keys())
    for code_csv, in db.execute(select(DataSource.scope_region_codes)).all():
        all_codes.update(_scope_to_codes(code_csv))
    region_options = [{"code": c, "name": region_map.get(c, c)} for c in sorted(all_codes)]
    region_options.insert(0, {"code": "", "name": "全部区域"})

    return {
        "items": items,
        "total": total,
        "page": page,
        "size": size,
        "region_options": region_options,
    }


@admin_ds_router.get("/regions", response_model=list[RegionCatalogItemOut])
def list_data_source_regions(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Return the full province -> city -> county -> township directory."""
    return region_catalog_items(db)


@admin_ds_router.get("/quality")
def data_source_quality(
    days: int = Query(7, ge=1, le=90),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("sources:read")),
):
    """Return read-only collection quality indicators from ``collector_runs``.

    ``success`` only describes collector execution. Zero-fetch streaks are
    exposed separately, so successful runs without collected content remain
    visible to operators.
    """
    cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days)
    sources = db.execute(
        select(DataSource.id, DataSource.name)
        .order_by(DataSource.priority.asc(), DataSource.id.asc())
    ).all()
    names = [source.name for source in sources]
    runs_by_name: dict[str, list[CollectorRun]] = {name: [] for name in names}
    if names:
        runs = db.execute(
            select(
                CollectorRun.id,
                CollectorRun.collector_name,
                CollectorRun.start_time,
                CollectorRun.fetched_raw,
                CollectorRun.created,
                CollectorRun.failed,
                CollectorRun.status,
            )
            .where(CollectorRun.collector_name.in_(names))
            .order_by(CollectorRun.start_time.desc(), CollectorRun.id.desc())
        ).all()
        for run in runs:
            runs_by_name.setdefault(run.collector_name, []).append(run)

    items = []
    for source in sources:
        all_source_runs = runs_by_name.get(source.name, [])
        source_runs = [run for run in all_source_runs if run.start_time >= cutoff]
        run_count = len(source_runs)
        latest = all_source_runs[0] if all_source_runs else None
        consecutive_failed_count = 0
        consecutive_empty_fetch_count = 0
        for run in all_source_runs:
            if run.status in {"failed", "error", "partial"} or run.failed > 0:
                consecutive_failed_count += 1
            else:
                break
        for run in all_source_runs:
            if run.fetched_raw == 0:
                consecutive_empty_fetch_count += 1
            else:
                break

        if latest is None:
            empty_fetch_risk = "unknown"
        elif consecutive_empty_fetch_count >= 3:
            empty_fetch_risk = "high"
        elif latest.fetched_raw == 0:
            empty_fetch_risk = "warning"
        else:
            empty_fetch_risk = "normal"

        items.append({
            "data_source_id": source.id,
            "collector_name": source.name,
            "latest_run_at": latest.start_time.isoformat() if latest else None,
            "run_count": run_count,
            "success_rate": round(sum(run.status == "success" for run in source_runs) / run_count, 4) if run_count else None,
            "fetched_nonzero_rate": round(sum(run.fetched_raw > 0 for run in source_runs) / run_count, 4) if run_count else None,
            "fetched_zero_rate": round(sum(run.fetched_raw == 0 for run in source_runs) / run_count, 4) if run_count else None,
            "created_nonzero_rate": round(sum(run.created > 0 for run in source_runs) / run_count, 4) if run_count else None,
            "fetched_raw_total": sum(run.fetched_raw for run in source_runs),
            "created_total": sum(run.created for run in source_runs),
            "latest_status": latest.status if latest else None,
            "latest_fetched_raw": latest.fetched_raw if latest else None,
            "latest_created": latest.created if latest else None,
            "consecutive_failed_count": consecutive_failed_count,
            "consecutive_empty_fetch_count": consecutive_empty_fetch_count,
            "empty_fetch_risk": empty_fetch_risk,
        })
    return {"days": days, "items": items}


@admin_ds_router.post("/test")
def test_data_source(
    body: dict,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """仅校验：构建采集器并真实抓取一次，不落库。返回 {ok, error, test}。"""
    err = _validate_create(body)
    if err:
        raise HTTPException(status_code=422, detail=err)
    type_ = body.get("type") or "generic_site"
    class_path = body.get("class_path") or _TYPE_CLASS_PATH.get(type_, _TYPE_CLASS_PATH["generic_site"])
    cfg, _ = _parse_config_json(body.get("config_json"))
    test = _build_test(class_path, cfg, data_source_key=body.get("key"))
    return {"ok": test.get("ok", False), "error": test.get("error"), "test": test}


@admin_ds_router.post("")
def create_data_source(
    body: dict,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """新增数据源：保存前进行真实抓取校验，校验失败不落库（返回 422 + 可读错误）。"""
    err = _validate_create(body)
    if err:
        raise HTTPException(status_code=422, detail=err)

    key = body["key"].strip()
    if db.scalar(select(DataSource).where(DataSource.key == key)):
        raise HTTPException(status_code=409, detail=f"key 已存在：{key}")

    name = body["name"].strip()
    type_ = body.get("type") or "generic_site"
    class_path = body.get("class_path") or _TYPE_CLASS_PATH.get(type_, _TYPE_CLASS_PATH["generic_site"])
    cfg, _ = _parse_config_json(body.get("config_json"))

    # —— 保存前的真实抓取校验（核心需求）——
    test = _build_test(class_path, cfg, data_source_key=key)
    media_crawler_source = _is_mediacrawler(class_path)
    foreign_source = _is_foreign(class_path)
    schedule_enabled = bool(
        body.get(
            "schedule_enabled",
            False if media_crawler_source or foreign_source else True,
        )
    )
    schedule_interval_minutes = int(
        body.get("schedule_interval_minutes", 30)
    )
    if not test.get("ok"):
        raise HTTPException(
            status_code=422,
            detail=test.get("error") or "抓取校验未通过，未创建数据源",
        )

    raw_cfg = body.get("config_json")
    config_json_str = raw_cfg if isinstance(raw_cfg, str) else json.dumps(cfg, ensure_ascii=False)
    with audit_write(
        db, action="CREATE", operator=current_user, request=request,
        resource_type="data_source",
        details={"key": key, "name": name, "type": type_, "class_path": class_path},
    ) as ctx:
        sync_region_codes(db, _scope_to_codes(body.get("scope_region_codes")))
        ds = DataSource(
            key=key,
            name=name,
            type=type_,
            class_path=class_path,
            enabled=bool(
                body.get("enabled", False if foreign_source else True)
            ),
            priority=int(body.get("priority", 50)),
            schedule_enabled=schedule_enabled,
            schedule_interval_minutes=schedule_interval_minutes,
            scope_region_codes=body.get("scope_region_codes") or None,
            config_json=config_json_str,
        )
        db.add(ds)
        db.commit()
        ctx["resource_id"] = str(ds.id)
    db.refresh(ds)
    return {
        **_serialize(
            ds,
            _region_map(db),
            region_keywords=_enabled_region_keywords(db),
        ),
        "test": test,
    }


@admin_ds_router.post("/schedule/batch")
def batch_update_schedule(
    body: dict,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """批量设置采集频率（仅 admin）。

    scope: "all" | "enabled_only"
    统一设置 schedule_enabled / schedule_interval_minutes，并按 PG now() 错峰重算
    next_collect_time（按 id 分散 0~4 分钟，避免集体同刻触发）。
    """
    scope = body.get("scope")
    if scope not in ("all", "enabled_only"):
        raise HTTPException(status_code=422, detail="scope 必须为 all 或 enabled_only")
    se = body.get("schedule_enabled")
    iv = body.get("schedule_interval_minutes")
    if iv is not None:
        try:
            iv = int(iv)
        except (TypeError, ValueError):
            raise HTTPException(status_code=422, detail="schedule_interval_minutes 必须为整数")
        if iv < 5:
            raise HTTPException(status_code=422, detail="schedule_interval_minutes 必须大于等于 5")
    if se is None and iv is None:
        raise HTTPException(
            status_code=422,
            detail="至少提供 schedule_enabled 或 schedule_interval_minutes 之一",
        )

    stmt = select(DataSource)
    if scope == "enabled_only":
        stmt = stmt.where(DataSource.enabled == True)
    targets = db.execute(stmt).scalars().all()
    with audit_write(
        db, action="UPDATE", operator=current_user, request=request,
        resource_type="data_source_schedule",
        details={"scope": scope, "schedule_enabled": se,
                 "schedule_interval_minutes": iv, "count": len(targets)},
    ):
        for ds in targets:
            if _is_foreign(ds.class_path) and se is True:
                # Foreign collection has an isolated manual endpoint in Phase 1.
                # Keep it out of the domestic scheduler even if a batch setting
                # is applied from the existing domestic UI.
                ds.schedule_enabled = False
                continue
            if se is not None:
                ds.schedule_enabled = bool(se)
            if iv is not None:
                ds.schedule_interval_minutes = iv
                if ds.schedule_enabled:
                    # 错峰：按 id 分散 0~4 分钟（与迁移初始化一致），规避集体同刻触发
                    ds.next_collect_time = text(
                        f"now() + make_interval(mins => {iv + (ds.id % 5)})"
                    )
        db.commit()
    return {"affected_count": len(targets)}


@admin_ds_router.get("/schedule/summary")
def schedule_summary(
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """返回当前调度频率状态：统一（uniform）/ 混合（mixed）。

    仅统计「启用且开启自动采集」的源；distribution 给出各间隔的源数量。
    """
    rows = db.execute(
        select(DataSource.schedule_interval_minutes, DataSource.schedule_enabled)
        .where(DataSource.enabled == True)
    ).all()
    enabled_auto = [r[0] for r in rows if r[1]]
    if not enabled_auto:
        return {
            "mode": "uniform",
            "interval_minutes": settings.collector_default_interval_minutes,
            "enabled_auto_count": 0,
        }
    uniq = set(enabled_auto)
    if len(uniq) == 1:
        return {
            "mode": "uniform",
            "interval_minutes": next(iter(uniq)),
            "enabled_auto_count": len(enabled_auto),
        }
    dist: dict = {}
    for v in enabled_auto:
        dist[v] = dist.get(v, 0) + 1
    return {"mode": "mixed", "distribution": dist, "enabled_auto_count": len(enabled_auto)}


@admin_ds_router.patch("/{ds_id}")
def update_data_source(
    ds_id: int,
    body: dict,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    ds = db.get(DataSource, ds_id)
    if not ds:
        raise HTTPException(status_code=404, detail="Data source not found")

    with audit_write(
        db, action="UPDATE", operator=current_user, request=request,
        resource_type="data_source", resource_id=str(ds_id),
        details={"changes": list(body.keys())},
    ):
        scope_codes = _scope_to_codes(ds.scope_region_codes)
        if "scope_region_codes" in body:
            scope_codes = _validated_scope_codes(body["scope_region_codes"])
            if _is_foreign(ds.class_path) and scope_codes:
                raise HTTPException(
                    status_code=422,
                    detail="foreign data source must not use region scope",
                )
            sync_region_codes(db, scope_codes)
            ds.scope_region_codes = ",".join(scope_codes) or None
            if _is_mediacrawler(ds.class_path) and "config_json" not in body:
                cfg, err = _parse_config_json(ds.config_json or "{}")
                if not err and isinstance(cfg, dict):
                    aligned = _align_mediacrawler_collection_mode(ds, cfg, scope_codes)
                    # 与下方 config_json 分支共用同一道校验：_align 会在 regional/national
                    # 之间翻转 collection_mode，若库中既有的 filter_mode/keyword_scope 与新
                    # 模式矛盾（如 national + region_only），此处必须拒绝。否则非法配置会静默
                    # 落库，直到下一次采集在 registry 装配阶段才抛 ValueError，表现为该源每个
                    # 调度周期失败一次（小红书 2026-08-07 15:40 采集失败即由此产生）。
                    merr = _validate_mediacrawler_config(aligned, ds.scope_region_codes)
                    if merr:
                        raise HTTPException(
                            status_code=422,
                            detail=(
                                f"{merr}；修改地域范围会同时把 collection_mode 切换为 "
                                f"{aligned.get('collection_mode')}，请一并调整 config_json "
                                "中的 filter_mode / keyword_scope"
                            ),
                        )
                    ds.config_json = json.dumps(aligned, ensure_ascii=False)
        if "enabled" in body and body["enabled"] is not None:
            ds.enabled = bool(body["enabled"])
        if "priority" in body and body["priority"] is not None:
            try:
                ds.priority = int(body["priority"])
            except (TypeError, ValueError):
                raise HTTPException(status_code=422, detail="priority 必须为整数")
        if "config_json" in body:
            raw = body["config_json"]
            if _is_mediacrawler(ds.class_path):
                if raw is None:
                    ds.config_json = "{}"
                elif isinstance(raw, str):
                    s = raw.strip()
                    cfg, err = _parse_config_json(s)
                    if err:
                        raise HTTPException(status_code=422, detail=err)
                    cfg = _align_mediacrawler_collection_mode(ds, cfg, scope_codes)
                    merr = _validate_mediacrawler_config(cfg, ds.scope_region_codes)
                    if merr:
                        raise HTTPException(status_code=422, detail=merr)
                    ds.config_json = json.dumps(cfg, ensure_ascii=False)
                elif isinstance(raw, dict):
                    raw = _align_mediacrawler_collection_mode(ds, raw, scope_codes)
                    merr = _validate_mediacrawler_config(raw, ds.scope_region_codes)
                    if merr:
                        raise HTTPException(status_code=422, detail=merr)
                    ds.config_json = json.dumps(raw, ensure_ascii=False)
                else:
                    raise HTTPException(status_code=422, detail="config_json must be a JSON object")
            elif _is_foreign(ds.class_path):
                if raw is None:
                    raise HTTPException(
                        status_code=422,
                        detail="foreign data source requires config_json",
                    )
                cfg, err = _parse_config_json(raw)
                if err:
                    raise HTTPException(status_code=422, detail=err)
                ferr = _validate_foreign_config(cfg)
                if ferr:
                    raise HTTPException(status_code=422, detail=ferr)
                ds.config_json = json.dumps(cfg, ensure_ascii=False)
            elif _is_generic(ds.class_path):
                # 通用型（GenericSiteCollector）：允许设置合法 config；禁止清空
                if raw is None:
                    raise HTTPException(status_code=422, detail="通用型采集器不能清空 config_json")
                if isinstance(raw, str):
                    s = raw.strip()
                    if s == "":
                        raise HTTPException(status_code=422, detail="通用型采集器不能清空 config_json")
                    try:
                        cfg = json.loads(s)
                    except json.JSONDecodeError:
                        raise HTTPException(status_code=422, detail="config_json 不是合法 JSON")
                    if not isinstance(cfg, dict):
                        raise HTTPException(status_code=422, detail="config_json 必须是 JSON 对象")
                    gerr = _validate_generic_config(cfg)
                    if gerr:
                        raise HTTPException(status_code=422, detail=gerr)
                    cerr = _validate_collection_config(cfg)
                    if cerr:
                        raise HTTPException(status_code=422, detail=cerr)
                    ds.config_json = s
                elif isinstance(raw, dict):
                    if not raw:
                        raise HTTPException(status_code=422, detail="通用型采集器不能清空 config_json")
                    gerr = _validate_generic_config(raw)
                    if gerr:
                        raise HTTPException(status_code=422, detail=gerr)
                    cerr = _validate_collection_config(raw)
                    if cerr:
                        raise HTTPException(status_code=422, detail=cerr)
                    try:
                        ds.config_json = json.dumps(raw, ensure_ascii=False)
                    except (TypeError, ValueError):
                        raise HTTPException(status_code=422, detail="config_json 序列化失败")
                else:
                    raise HTTPException(status_code=422, detail="config_json 格式不支持")
            else:
                # 专用型采集器：config_json 仅允许「空配置」或「仅含策略键」
                # （max_items / filter_mode / keyword_scope，Phase DataSource-Config-1）。
                # 剥离策略键后若仍含其他非空键 → 拒绝（保持专用型约束）。
                if raw is None:
                    ds.config_json = "{}"
                elif isinstance(raw, str):
                    s = raw.strip()
                    if s in ("", "{}"):
                        ds.config_json = "{}"
                    else:
                        try:
                            cfg = json.loads(s)
                        except json.JSONDecodeError:
                            raise HTTPException(status_code=422, detail=DEDICATED_EMPTY_HINT)
                        if not isinstance(cfg, dict):
                            raise HTTPException(status_code=422, detail=DEDICATED_EMPTY_HINT)
                        eff = {k: v for k, v in cfg.items() if k not in DEDICATED_ALLOWED_KEYS}
                        if eff:
                            raise HTTPException(status_code=422, detail=DEDICATED_EMPTY_HINT)
                        cerr = _validate_collection_config(cfg)
                        if cerr:
                            raise HTTPException(status_code=422, detail=cerr)
                        ds.config_json = s  # 保留含策略键/采集模式的原配置（供 registry 注入 source_config）
                elif isinstance(raw, dict):
                    if not raw:
                        ds.config_json = "{}"
                    else:
                        eff = {k: v for k, v in raw.items() if k not in DEDICATED_ALLOWED_KEYS}
                        if eff:
                            raise HTTPException(status_code=422, detail=DEDICATED_EMPTY_HINT)
                        cerr = _validate_collection_config(raw)
                        if cerr:
                            raise HTTPException(status_code=422, detail=cerr)
                        try:
                            ds.config_json = json.dumps(raw, ensure_ascii=False)
                        except (TypeError, ValueError):
                            raise HTTPException(status_code=422, detail="config_json 序列化失败")
                else:
                    raise HTTPException(status_code=422, detail=DEDICATED_EMPTY_HINT)

        # —— Phase DataSource-Schedule-1：采集频率字段 ——
        if "schedule_enabled" in body and body["schedule_enabled"] is not None:
            requested_schedule = bool(body["schedule_enabled"])
            if _is_foreign(ds.class_path) and requested_schedule:
                cfg, err = _parse_config_json(ds.config_json or "{}")
                ferr = err or _validate_foreign_config(cfg)
                if ferr:
                    raise HTTPException(status_code=422, detail=ferr)
                # Foreign scheduling remains opt-in and is never enabled by
                # domestic batch settings or legacy defaults.
                ds.schedule_enabled = False
            else:
                ds.schedule_enabled = requested_schedule
        if "schedule_interval_minutes" in body and body["schedule_interval_minutes"] is not None:
            try:
                iv = int(body["schedule_interval_minutes"])
            except (TypeError, ValueError):
                raise HTTPException(status_code=422, detail="schedule_interval_minutes 必须为整数")
            if iv < 5:
                raise HTTPException(status_code=422, detail="schedule_interval_minutes 必须大于等于 5")
            ds.schedule_interval_minutes = iv
        # 修改周期 或 由关闭改为启用 时，基于 PG now() 重算下次采集时间（规避时区偏差 R3）
        if "schedule_interval_minutes" in body or (
            body.get("schedule_enabled") is True and ds.schedule_enabled
        ):
            ds.next_collect_time = text(
                f"now() + make_interval(mins => {ds.schedule_interval_minutes})"
            )

        if _is_foreign(ds.class_path) and (
            body.get("enabled") is True or ds.enabled and body.get("schedule_enabled") is True
        ):
            cfg, err = _parse_config_json(ds.config_json or "{}")
            ferr = err or _validate_foreign_config(cfg)
            if ferr:
                raise HTTPException(status_code=422, detail=ferr)

        db.commit()
    db.refresh(ds)
    region_map = _region_map(db)
    return _serialize(
        ds,
        region_map,
        region_keywords=_enabled_region_keywords(db),
    )


def _run_to_dict(r: CollectorRun) -> dict:
    """逐源采集记录（CollectorRun）序列化为前端历史 / 批次明细共用的字段。"""
    return {
        "id": r.id,
        "collector_name": r.collector_name,
        "scope": getattr(r, "scope", "domestic"),
        "proxy_used": bool(getattr(r, "proxy_used", False)),
        "batch_id": r.batch_id,
        "trigger_type": r.trigger_type,
        "start_time": r.start_time.isoformat() if r.start_time else None,
        "end_time": r.end_time.isoformat() if r.end_time else None,
        "fetched_raw": r.fetched_raw,
        "upstream_total": getattr(r, "upstream_total", None),
        "upstream_returned": getattr(r, "upstream_returned", 0) or 0,
        "created": r.created,
        "duplicate": getattr(r, "duplicate", 0) or 0,
        "analyzed": r.analyzed,
        "failed": r.failed,
        "acknowledged": getattr(r, "acknowledged", 0) or 0,
        "unconfirmed": getattr(r, "unconfirmed", 0) or 0,
        "ack_status": getattr(r, "ack_status", "not_applicable"),
        "comments_seen": getattr(r, "comments_seen", 0) or 0,
        "comments_skipped": getattr(r, "comments_skipped", 0) or 0,
        "admission_filtered": getattr(r, "admission_filtered", 0) or 0,
        "status": r.status,
        "error_msg": r.error_msg,
    }


@admin_ds_router.get("/{ds_id}/runs")
def data_source_runs(
    ds_id: int,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("sources:read")),
):
    """复用 collector_runs（按 collector_name == ds.name）查询该源最近采集记录。"""
    ds = db.get(DataSource, ds_id)
    if not ds:
        raise HTTPException(status_code=404, detail="Data source not found")

    run_scope = "foreign" if _is_foreign(ds.class_path) else "domestic"
    stmt = select(CollectorRun).where(
        CollectorRun.collector_name == ds.name,
        CollectorRun.scope == run_scope,
    )
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.order_by(CollectorRun.start_time.desc())
        .offset((page - 1) * size)
        .limit(size)
    ).all()
    return {"items": [_run_to_dict(r) for r in rows], "total": total, "page": page, "size": size}


@admin_ds_router.get("/collection-logs")
def collection_logs(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    trigger_type: str | None = Query(None, description="manual / scheduled"),
    status: str | None = Query(None, description="success / partial / failed / running"),
    from_: str | None = Query(None, alias="from", description="ISO 起始时间（含）"),
    to: str | None = Query(None, description="ISO 结束时间（含）"),
    scope: str = Query("domestic", description="domestic / foreign"),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("sources:read")),
):
    """采集日志：按批次（batch_id；历史按 start_time 兼容）聚合每次采集触发的整体记录。

    批次键 = COALESCE(batch_id, start_time::text)。当前数据量小（百级批次），
    全量聚合后在 Python 侧做筛选与分页，逻辑更清晰。
    """
    if scope not in {"domestic", "foreign"}:
        raise HTTPException(status_code=422, detail="scope must be domestic or foreign")
    scoped_runs = select(CollectorRun).where(CollectorRun.scope == scope).subquery()
    batch_key = func.coalesce(
        scoped_runs.c.batch_id,
        func.cast(scoped_runs.c.start_time, String),
    ).label("batch_key")
    rows = db.execute(
        select(
            batch_key,
            func.min(scoped_runs.c.start_time).label("started_at"),
            func.max(scoped_runs.c.end_time).label("finished_at"),
            func.count(scoped_runs.c.id).label("source_count"),
            func.sum(scoped_runs.c.fetched_raw).label("fetched_raw"),
            func.sum(scoped_runs.c.upstream_total).label("upstream_total"),
            func.sum(scoped_runs.c.upstream_returned).label("upstream_returned"),
            func.sum(scoped_runs.c.created).label("created"),
            func.sum(scoped_runs.c.duplicate).label("duplicate"),
            func.sum(scoped_runs.c.analyzed).label("analyzed"),
            func.sum(scoped_runs.c.acknowledged).label("acknowledged"),
            func.sum(scoped_runs.c.unconfirmed).label("unconfirmed"),
            func.sum(scoped_runs.c.comments_seen).label("comments_seen"),
            func.sum(scoped_runs.c.comments_skipped).label("comments_skipped"),
            func.sum(scoped_runs.c.admission_filtered).label("admission_filtered"),
            func.max(scoped_runs.c.ack_status).label("ack_status"),
            func.sum(case((scoped_runs.c.status == "success", 1), else_=0)).label("success_count"),
            func.sum(case((scoped_runs.c.status == "partial", 1), else_=0)).label("partial_count"),
            func.sum(case((scoped_runs.c.status == "warning", 1), else_=0)).label("warning_count"),
            func.sum(case((scoped_runs.c.status.in_(["failed", "error"]), 1), else_=0)).label("failed_count"),
            func.sum(case((scoped_runs.c.status == "running", 1), else_=0)).label("running_count"),
            func.max(scoped_runs.c.trigger_type).label("trigger_type"),
            func.max(scoped_runs.c.batch_id).label("batch_id"),
        ).group_by(batch_key)
    ).all()

    def _parse_dt(s: str | None):
        if not s:
            return None
        s = s.strip()
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        try:
            return datetime.fromisoformat(s)
        except ValueError:
            return None

    def _batch_status(r) -> str:
        if r.running_count and r.running_count > 0:
            return "running"
        if r.failed_count and r.failed_count > 0:
            return "failed"
        if r.partial_count and r.partial_count > 0:
            return "partial"
        if r.warning_count and r.warning_count > 0:
            return "warning"
        return "success"

    def _to_item(r):
        started = r.started_at
        finished = r.finished_at
        duration = None
        if started and finished:
            duration = (finished - started).total_seconds()
        return {
            "batch_key": r.batch_key,
            "batch_id": r.batch_id,
            "trigger_type": r.trigger_type,
            "started_at": started.isoformat() if started else None,
            "finished_at": finished.isoformat() if finished else None,
            "duration_seconds": duration,
            "source_count": r.source_count or 0,
            "success_count": r.success_count or 0,
            "partial_count": r.partial_count or 0,
            "warning_count": r.warning_count or 0,
            "failed_count": r.failed_count or 0,
            "running_count": r.running_count or 0,
            "fetched_raw": int(r.fetched_raw or 0),
            "upstream_total": int(r.upstream_total or 0),
            "upstream_returned": int(r.upstream_returned or 0),
            "created": int(r.created or 0),
            "duplicate": int(r.duplicate or 0),
            "analyzed": int(r.analyzed or 0),
            "acknowledged": int(r.acknowledged or 0),
            "unconfirmed": int(r.unconfirmed or 0),
            "comments_seen": int(r.comments_seen or 0),
            "comments_skipped": int(r.comments_skipped or 0),
            "admission_filtered": int(r.admission_filtered or 0),
            "ack_status": r.ack_status or "not_applicable",
            "status": _batch_status(r),
        }

    items = [_to_item(r) for r in rows]
    if trigger_type:
        items = [i for i in items if (i["trigger_type"] or "") == trigger_type]
    if status:
        items = [i for i in items if i["status"] == status]
    f_from = _parse_dt(from_)
    f_to = _parse_dt(to)
    if f_from is not None:
        items = [i for i in items if i["started_at"] and _parse_dt(i["started_at"]) and _parse_dt(i["started_at"]) >= f_from]
    if f_to is not None:
        items = [i for i in items if i["started_at"] and _parse_dt(i["started_at"]) and _parse_dt(i["started_at"]) <= f_to]
    items.sort(key=lambda i: (i["started_at"] is None, i["started_at"] or ""), reverse=True)
    total = len(items)
    start = (page - 1) * size
    return {"items": items[start:start + size], "total": total, "page": page, "size": size}


@admin_ds_router.get("/collection-logs/{batch_key}/runs")
def collection_log_runs(
    batch_key: str,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    scope: str = Query("domestic", description="domestic / foreign"),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("sources:read")),
):
    """某次采集批次下各数据源的逐源明细（复用 _run_to_dict 序列化）。

    batch_key 为 COALESCE(batch_id, start_time::text)：新数据用 batch_id，
    历史数据用 start_time 文本。前端传参需 encodeURIComponent（start_time 含空格）。
    """
    if scope not in {"domestic", "foreign"}:
        raise HTTPException(status_code=422, detail="scope must be domestic or foreign")
    key_expr = func.coalesce(CollectorRun.batch_id, func.cast(CollectorRun.start_time, String))
    stmt = select(CollectorRun).where(
        key_expr == batch_key,
        CollectorRun.scope == scope,
    )
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.order_by(CollectorRun.start_time.desc(), CollectorRun.id)
        .offset((page - 1) * size)
        .limit(size)
    ).all()
    return {"items": [_run_to_dict(r) for r in rows], "total": total, "page": page, "size": size}
