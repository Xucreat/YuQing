"""采集器注册表 / 表驱动装配（Phase 3）。

职责：
1. 动态导入采集器类（import_class），避免中心代码 import 全部子类。
2. resolve_collectors(db, collector_type)：优先读 data_sources 表（enabled，
     按 priority 排序）；**表为空或异常时回退到内置 DEFAULT_SOURCES**（灰度切换，
     生产零停机）。新增数据源 = 插入一行 + （可选）写一个薄采集器类，无需改本文件。
3. 为每个采集器实例注入 scope_region_codes（供 CollectorService 绑定 region_id）
     与 data_source_key（审计用）。

设计约束（延续既有约定）：
  - 不修改数据库结构逻辑；data_sources 由 alembic 迁移创建。
  - 仅在 resolve_collectors 中读取 data_sources；其余流程零耦合。

可靠性约束（Phase 3 优化）：
  - config_json 解析失败（非法 JSON / 非对象）**不再静默兜底为 {}**，
    而是抛出 ConfigParseError，交由调用方记为装配失败并暴露。
  - 装配失败的源不再被静默丢弃，而是进入 ResolvedCollectors.failures，
    由采集主流程写入 CollectorRun(status=failed) 使错误在采集日志中可见。
  - resolve_collectors 保持"仅返回采集器列表"的旧契约（测试 / 脚本依赖）；
    需要失败明细时改用 resolve_collectors_verbose。
"""
from __future__ import annotations

import importlib
import json
import logging
from dataclasses import dataclass, field
from typing import Collection, List, Optional

from sqlalchemy.orm import Session

from app.collectors.base import BaseCollector
from app.collectors.source_config import (
    STRATEGY_KEYS,
    DataSourceConfig,
    validate_data_source_config,
)

logger = logging.getLogger(__name__)

# 观测状态：最近一次数据源发现是否因 DB 异常而降级到 DEFAULT_SOURCES。
# 供 /health 等健康检查读取，避免「静默降级」导致运维无法察觉
# （Phase DataSource-Schedule-Fix-1：DB 查询失败时必须可观测，禁止静默）。
# True = 上次发现时 DB 查询异常，已回退内置默认源（采集列表可能与 DB 配置不一致）。
last_discovery_degraded: bool = False
last_discovery_error: Optional[str] = None

# ---------------------------------------------------------------------------
# 内置默认源（灰度回退）：等价于「迁移前 if/else 装配」。一旦 data_sources 表
# 存在且非空，resolve_collectors 优先读表，本定义不再参与生产装配。
# 字段与 DataSource 模型一致；config_json 对 bespoke 采集器为 "{}"（沿用类内默认）。
# ---------------------------------------------------------------------------
DEFAULT_SOURCES: List[dict] = [
    {
        "key": "government", "name": "大厂县政府网站", "type": "gov_site",
        "class_path": "app.collectors.government_collector.GovernmentCollector",
        "enabled": True, "priority": 10, "scope_region_codes": "131028",
        "config_json": "{}",
    },
    {
        "key": "baidu_news", "name": "百度新闻", "type": "search",
        "class_path": "app.collectors.baidu_news_collector.BaiduNewsCollector",
        "enabled": True, "priority": 20, "scope_region_codes": "",
        "config_json": "{}",
    },
    {
        "key": "hebei_news", "name": "河北新闻网", "type": "news_site",
        "class_path": "app.collectors.hebei_news_collector.HebeiNewsCollector",
        "enabled": True, "priority": 30, "scope_region_codes": "130000",
        "config_json": "{}",
    },
    {
        "key": "xinhua", "name": "新华网", "type": "news_site",
        "class_path": "app.collectors.xinhua_collector.XinhuaCollector",
        "enabled": True, "priority": 40, "scope_region_codes": "",
        "config_json": "{}",
    },
    {
        "key": "people", "name": "人民网", "type": "news_site",
        "class_path": "app.collectors.people_collector.PeopleCollector",
        "enabled": True, "priority": 50, "scope_region_codes": "",
        "config_json": "{}",
    },
    {
        "key": "chinanews", "name": "中国新闻网", "type": "rss",
        "class_path": "app.collectors.chinanews_collector.ChinanewsCollector",
        "enabled": True, "priority": 55, "scope_region_codes": "",
        "config_json": "{}",
    },
    {
        "key": "hebei_daily", "name": "河北日报", "type": "news_site",
        "class_path": "app.collectors.hebei_daily_collector.HebeiDailyCollector",
        "enabled": True, "priority": 60, "scope_region_codes": "130000",
        "config_json": "{}",
    },
    {
        "key": "changcheng", "name": "长城网", "type": "news_site",
        "class_path": "app.collectors.changcheng_collector.ChangchengCollector",
        "enabled": True, "priority": 65, "scope_region_codes": "130000",
        "config_json": "{}",
    },
    {
        "key": "hebei_gov", "name": "河北省人民政府", "type": "gov_site",
        "class_path": "app.collectors.hebei_gov_collector.HebeiGovCollector",
        "enabled": True, "priority": 70, "scope_region_codes": "130000",
        "config_json": "{}",
    },
]

_CLASS_CACHE: dict = {}


def import_class(class_path: str) -> type:
    """惰性动态导入采集器类：'module.path.ClassName' -> class。"""
    if class_path in _CLASS_CACHE:
        return _CLASS_CACHE[class_path]
    module_path, _, cls_name = class_path.rpartition(".")
    if not module_path or not cls_name:
        raise ImportError(f"非法 class_path: {class_path}")
    module = importlib.import_module(module_path)
    cls = getattr(module, cls_name)
    _CLASS_CACHE[class_path] = cls
    return cls


def parse_codes(csv: Optional[str]) -> Optional[List[str]]:
    """'130100,131028' -> ['130100','131028']；'' / None / 'ALL' -> None（全国）。"""
    if csv is None:
        return None
    s = csv.strip()
    if s == "" or s.upper() == "ALL":
        return None
    return [c.strip() for c in s.split(",") if c.strip()]


class ConfigParseError(Exception):
    """config_json 解析/校验失败的明确错误（区别于其他装配异常）。"""


def _parse_config(config_json: Optional[str]) -> dict:
    """解析 config_json 为 dict。

    - None / '' / '{}' / 非字符串空值 -> 视为空配置，返回 {}。
    - 合法 JSON 对象 -> 返回 dict。
    - 非法 JSON / 非对象 -> **抛出 ConfigParseError**（不再静默兜底为 {}），
      交由上层记为装配失败，避免"看起来正常但实为错误配置"的静默失败。
    """
    if config_json is None:
        return {}
    if isinstance(config_json, str):
        s = config_json.strip()
        if s == "":
            return {}
        try:
            cfg = json.loads(s)
        except json.JSONDecodeError as e:
            raise ConfigParseError(f"config_json 不是合法 JSON：{e}")
    else:
        # 非字符串（理论不应出现）：直接当作对象处理
        cfg = config_json
    if not isinstance(cfg, dict):
        raise ConfigParseError("config_json 必须是 JSON 对象")
    return cfg


def _split_strategy_keys(cfg: dict) -> dict:
    """剥离策略键（Phase DataSource-Config-1），返回可安全用于 ``cls(**kwargs)`` 的配置。

    ``max_items`` / ``filter_mode`` / ``keyword_scope`` 是**采集策略**参数，
    不是采集器构造函数参数。专用型采集器（XinhuaCollector 等）的 ``__init__``
    只接受 urls / keywords，若把策略键透传过去会直接 TypeError 导致该源装配失败。
    因此这里先剥离，策略键改由 ``collector.source_config`` 承载（见 _attach_meta）。

    注：``max_articles`` 等 GenericSiteCollector 既有键**不在剥离范围**，
    继续按原路径进入构造函数，保证 27 个存量数据源零影响。
    """
    return {k: v for k, v in cfg.items() if k not in STRATEGY_KEYS}


def _attach_meta(collector: BaseCollector, meta: dict, cfg: Optional[dict] = None) -> BaseCollector:
    """注入 scope_region_codes（区域绑定）、data_source_key（审计）与 source_config（采集参数）。"""
    collector.scope_region_codes = parse_codes(meta.get("scope_region_codes"))
    if meta.get("key"):
        collector.data_source_key = meta["key"]
    # 注入**完整** config_json（含 max_articles 等既有键），供采集器按需读取；
    # 未注入时采集器沿用 BaseCollector.source_config 空配置 = 旧行为。
    collector.source_config = DataSourceConfig(cfg or {}, source_key=meta.get("key"))
    return collector


@dataclass
class ResolvedCollectors:
    """表驱动装配结果：成功实例 + 装配失败明细（用于暴露，不静默丢弃）。"""
    collectors: List[BaseCollector] = field(default_factory=list)
    failures: List[dict] = field(default_factory=list)  # {key, name, class_path, error}


def _resolve_core(
    db: Optional[Session],
    collector_type: Optional[str],
    include_data_source_keys: Optional[Collection[str]] = None,
    exclude_data_source_keys: Optional[Collection[str]] = None,
) -> ResolvedCollectors:
    """核心装配逻辑（供 resolve_collectors / resolve_collectors_verbose 复用）。

    装配失败的源不再被静默吞掉，而是记入 failures，交由调用方暴露
    （如写入 CollectorRun.status=failed，使其在采集日志中可见）。
    """
    global last_discovery_degraded, last_discovery_error
    result = ResolvedCollectors()

    # mock 离线演示：直接返回单个 MockCollector（无失败风险）
    if collector_type and collector_type.lower() == "mock":
        from app.collectors.mock_collector import MockCollector
        result.collectors.append(MockCollector())
        return result

    rows = None
    if db is not None:
        try:
            from app.collectors.data_source_repository import enabled_sources

            # 仅选取装配所需字段（禁止 SELECT *）：查询条件统一收敛到
            # data_source_repository.enabled_sources，避免 scheduler 与 registry
            # 两处重复维护 enabled 过滤（Phase DataSource-Schedule-Fix-2）。
            rows = enabled_sources(db)
            # DB 读取成功（无论是否有启用源），清除降级标记。
            last_discovery_degraded = False
            last_discovery_error = None
        except Exception as exc:  # 表不存在/连接异常 -> 灰度回退（但必须可观测）
            logger.error(
                "DataSource registry DB load failed. "
                "collector discovery degraded to DEFAULT_SOURCES. error=%s",
                exc,
            )
            last_discovery_degraded = True
            last_discovery_error = f"{type(exc).__name__}: {exc}"
            rows = None

    if not rows:
        # 灰度回退：内置默认源定义（DB 为空或不可用时）
        logger.warning(
            "data_sources 为空/不可用，使用内置默认源定义（%d 个）。degraded=%s",
            len(DEFAULT_SOURCES), last_discovery_degraded,
        )
        rows = DEFAULT_SOURCES

    include_keys = set(include_data_source_keys or ())
    exclude_keys = set(exclude_data_source_keys or ())
    if include_data_source_keys is not None or exclude_data_source_keys is not None:
        rows = [
            row for row in rows
            if (
                (row.get("key") if isinstance(row, dict) else row.key) in include_keys
                if include_data_source_keys is not None
                else True
            )
            and (
                (row.get("key") if isinstance(row, dict) else row.key) not in exclude_keys
                if exclude_data_source_keys is not None
                else True
            )
        ]

    for row in rows:
        # row 可能是 ORM 对象（来自表）或 dict（来自 DEFAULT_SOURCES 回退）
        if isinstance(row, dict):
            meta = row
        else:
            meta = {
                "key": row.key,
                "name": row.name,
                "class_path": row.class_path,
                "scope_region_codes": row.scope_region_codes,
                "config_json": row.config_json,
            }
        try:
            cls = import_class(meta["class_path"])
            cfg = _parse_config(meta.get("config_json"))  # 非法 JSON -> ConfigParseError
            if getattr(cls, "data_source_key", None) == "weibo_mediacrawler":
                # Reuse the API contract at the registry boundary so direct DB
                # configuration cannot silently downgrade or reach the ctor.
                validate_data_source_config(cfg)
            # 策略键不进构造函数，避免专用型采集器 TypeError（见 _split_strategy_keys）
            collector = cls(**_split_strategy_keys(cfg))  # 未知/错误参数 -> TypeError 等
            result.collectors.append(_attach_meta(collector, meta, cfg))
        except ConfigParseError as exc:
            logger.error(
                "数据源配置解析失败 key=%s class=%s err=%s",
                meta.get("key"), meta.get("class_path"), exc,
            )
            result.failures.append({
                "key": meta.get("key"),
                "name": meta.get("name"),
                "class_path": meta.get("class_path"),
                "error": f"配置解析失败：{exc}",
            })
        except Exception as exc:
            logger.error(
                "装配数据源失败 key=%s class=%s err=%s",
                meta.get("key"), meta.get("class_path"),
                f"{type(exc).__name__}: {exc}",
            )
            result.failures.append({
                "key": meta.get("key"),
                "name": meta.get("name"),
                "class_path": meta.get("class_path"),
                "error": f"{type(exc).__name__}: {exc}",
            })
    return result


def resolve_collectors(
    db: Optional[Session] = None,
    collector_type: Optional[str] = None,
    include_data_source_keys: Optional[Collection[str]] = None,
    exclude_data_source_keys: Optional[Collection[str]] = None,
) -> List[BaseCollector]:
    """表驱动装配采集器（向后兼容旧契约）。

    仅返回成功装配的采集器列表；装配失败的源被记入 failures 但此处
    不暴露（保持与历史测试 / 脚本一致的行为）。需要失败明细时
    请改用 resolve_collectors_verbose。
    """
    return _resolve_core(
        db,
        collector_type,
        include_data_source_keys,
        exclude_data_source_keys,
    ).collectors


def resolve_collectors_verbose(
    db: Optional[Session] = None,
    collector_type: Optional[str] = None,
    include_data_source_keys: Optional[Collection[str]] = None,
    exclude_data_source_keys: Optional[Collection[str]] = None,
) -> ResolvedCollectors:
    """返回 (成功装配的采集器, 装配失败明细)。

    供采集主流程（CollecterService）暴露装配失败——失败明细会被写入
    CollectorRun(status=failed)，使"该源完全没采集"的异常在采集日志中可见，
    而不是静默消失。
    """
    return _resolve_core(
        db,
        collector_type,
        include_data_source_keys,
        exclude_data_source_keys,
    )
