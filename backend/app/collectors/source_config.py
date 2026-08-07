"""数据源采集参数统一读取工具（Phase DataSource-Config-1）。

背景
----
部分采集器把「单次最大采集量 / 过滤模式 / 关键词范围」硬编码在类内常量里
（如 ``MAX_ARTICLES = 10``），场景一变只能改代码。本模块把这些参数的**读取**
统一外移到 ``data_sources.config_json``，采集流程与 Collector 类型体系保持不变。

设计约束（本阶段严格遵守）
--------------------------
1. 只提供「读取能力」，不改采集流程、不改数据库结构、不新增字段。
2. **缺省即旧行为**：配置缺失 / 为空 / 非法时，一律回退调用方给的默认值，
   保证历史数据源（27 个 GenericSite + 5 个专用型）零改动继续按原逻辑运行。
3. **防御式解析**：单个键的类型错误（如 ``max_items: "abc"``）只记 warning 并
   降级到默认值，不让一次采集因为一处配置笔误整体失败。
   （注意与 registry 的区别：``config_json`` 整体非法 JSON 属结构性错误，
   仍由 ``registry.ConfigParseError`` 抛出并记为装配失败，此处不兜底。）

配置示例
--------
``data_sources.config_json``::

    {
      "max_items": 50,
      "filter_mode": "region_or_topic",
      "keyword_scope": "region_topic"
    }
"""
from __future__ import annotations

import logging
from typing import Any, Iterable, List, Optional, Sequence, Tuple

from app.collectors.mediacrawler_platform import (
    FORBIDDEN_MEDIACRAWLER_CONFIG_KEYS,
    MEDIACRAWLER_CONFIG_KEYS,
    get_mediacrawler_platform_spec,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 策略键（本阶段配置化的三个参数）
#
# 这些键**不是**采集器构造函数参数：registry 装配时会先把它们从 config_json
# 中剥离，再执行 ``cls(**cfg)``，否则专用型采集器（其 __init__ 只接受 urls /
# keywords）会因未知关键字参数直接 TypeError 装配失败。剥离后仍以完整配置
# 构造 DataSourceConfig 注入 collector.source_config，由采集器按需读取。
# ---------------------------------------------------------------------------
STRATEGY_KEYS: frozenset = frozenset({"max_items", "filter_mode", "keyword_scope"})

# max_items 的历史别名：GenericSiteCollector 早已使用 max_articles，
# 生产库中 27 个数据源在用。新键优先，旧键继续生效，不做数据迁移。
MAX_ITEMS_ALIASES: Tuple[str, ...] = ("max_articles",)

# 过滤模式合法取值（见 common.matches_region_topic）。
FILTER_MODES: frozenset = frozenset({"region_only", "region_or_topic", "topic_only"})

# 关键词范围合法取值。
KEYWORD_SCOPES: frozenset = frozenset({"region", "region_topic", "topic"})
KEYWORD_SCOPE_ALIASES: dict[str, str] = {
    "region_only": "region",
    "topic_only": "topic",
}

# ---------------------------------------------------------------------------
# 采集模式（Phase DataSource-National-Mode-3）
#
# 让数据源在 config_json 中**显式声明**其采集范围，替代「scope_region_codes 为空即全国」
# 的隐式推断（见 opinion_region_service.is_national_scope）。National-Mode-4 将消费本语义，
# 本阶段只负责配置化与合法性校验，不改变采集/准入/聚合行为。
# ---------------------------------------------------------------------------
# 允许值：区域模式 / 全国模式。
COLLECTION_MODES: frozenset = frozenset({"regional", "national"})
COLLECTION_SCOPES: frozenset = COLLECTION_MODES
# 缺省采集模式：区域（与历史行为一致；旧数据无 collection_mode 即按 regional 解释）。
DEFAULT_COLLECTION_MODE: str = "regional"
# 保留历史常量供兼容调用方使用；MediaCrawler national 不再用它们限制
# keyword_scope/filter_mode。采集覆盖范围与过滤策略由不同配置键分别负责。
NATIONAL_FILTER_MODES: frozenset = frozenset({"topic_only"})
# 历史 canonical national keyword scope。
NATIONAL_KEYWORD_SCOPES: frozenset = frozenset({"topic"})

# ---------------------------------------------------------------------------
# 各采集器「历史默认过滤策略」只读镜像（Phase DataSource-Filter-Config-4）
#
# 用途：前端展示「实际生效过滤策略」与「策略来源（配置 vs 采集器默认）」时，
#       需要回退到各采集器在 fetch() 中传给 cfg.filter_mode()/keyword_scope() 的默认值。
#
# 约束：本映射**逐字镜像**各 collector fetch() 内的默认实参，仅用于只读展示，
#       **不参与采集逻辑**；修改采集器默认行为时须同步此处，否则展示会与实际不符。
#       未列入本表的采集器（如 Government/Hebei* 等）视为「不应用本过滤策略」。
# ---------------------------------------------------------------------------
COLLECTOR_DEFAULT_STRATEGY: dict = {
    "app.collectors.baidu_news_collector.BaiduNewsCollector": ("region_only", "region"),
    "app.collectors.xinhua_collector.XinhuaCollector": ("region_or_topic", None),
    "app.collectors.people_collector.PeopleCollector": ("region_or_topic", None),
    "app.collectors.chinanews_collector.ChinanewsCollector": ("region_or_topic", None),
    "app.collectors.generic_site.GenericSiteCollector": ("region_only", None),
}
# 不应用 filter_mode/keyword_scope 策略的采集器（内置/全量逻辑）。
NON_FILTER_STRATEGY_CLASS_PATHS: frozenset = frozenset({
    "app.collectors.government_collector.GovernmentCollector",
    "app.collectors.hebei_news_collector.HebeiNewsCollector",
    "app.collectors.hebei_daily_collector.HebeiDailyCollector",
    "app.collectors.changcheng_collector.ChangchengCollector",
    "app.collectors.hebei_gov_collector.HebeiGovCollector",
    "app.collectors.weibo_octopus_collector.WeiboOctopusCollector",
    "app.collectors.grok_collector.GrokCollector",
})


class DataSourceConfig:
    """``data_sources.config_json`` 的只读访问器。

    避免每个采集器重复写 ``int(cfg.get("x", default))`` 与异常处理。
    所有 getter 遵循同一约定：**取不到 / 取到非法值 → 返回 default**。
    """

    __slots__ = ("_data", "_source_key")

    def __init__(self, raw: Optional[dict] = None, source_key: Optional[str] = None) -> None:
        self._data: dict = dict(raw) if isinstance(raw, dict) else {}
        # 仅用于日志定位是哪个数据源配置写错了。
        self._source_key: str = source_key or "-"

    # -- 基础 ---------------------------------------------------------------
    def __contains__(self, key: str) -> bool:
        return key in self._data

    def __repr__(self) -> str:
        return f"<DataSourceConfig key={self._source_key!r} keys={sorted(self._data)}>"

    @property
    def raw(self) -> dict:
        """返回配置副本（只读语义，调用方改动不影响本对象）。"""
        return dict(self._data)

    def has(self, key: str, aliases: Sequence[str] = ()) -> bool:
        """key 或其别名是否被显式配置过（值为 null 视为未配置）。"""
        return self._lookup(key, aliases)[0] is not None

    def _lookup(self, key: str, aliases: Sequence[str] = ()) -> Tuple[Any, str]:
        """按 key → aliases 顺序取第一个非 None 值，返回 (值, 命中的键名)。"""
        for name in (key, *aliases):
            value = self._data.get(name)
            if value is not None:
                return value, name
        return None, key

    def _warn(self, name: str, value: Any, expect: str, default: Any) -> None:
        logger.warning(
            "数据源配置项非法，已回退默认值：source=%s key=%s value=%r 期望=%s default=%r",
            self._source_key, name, value, expect, default,
        )

    # -- getters ------------------------------------------------------------
    def get_int(
        self,
        key: str,
        default: Optional[int] = None,
        *,
        aliases: Sequence[str] = (),
        minimum: Optional[int] = None,
    ) -> Optional[int]:
        """读取整数配置。非数字 / 小于 minimum → 回退 default 并记 warning。"""
        value, name = self._lookup(key, aliases)
        if value is None:
            return default
        try:
            # 显式排除 bool（Python 中 bool 是 int 子类，True 会被当作 1）。
            if isinstance(value, bool):
                raise TypeError("bool 不是合法整数配置")
            parsed = int(value)
        except (TypeError, ValueError):
            self._warn(name, value, "整数", default)
            return default
        if minimum is not None and parsed < minimum:
            self._warn(name, value, f"整数 >= {minimum}", default)
            return default
        return parsed

    def get_float(
        self,
        key: str,
        default: Optional[float] = None,
        *,
        aliases: Sequence[str] = (),
        minimum: Optional[float] = None,
    ) -> Optional[float]:
        """读取浮点配置。非数字 / 小于 minimum → 回退 default 并记 warning。"""
        value, name = self._lookup(key, aliases)
        if value is None:
            return default
        try:
            if isinstance(value, bool):
                raise TypeError("bool 不是合法浮点配置")
            parsed = float(value)
        except (TypeError, ValueError):
            self._warn(name, value, "数值", default)
            return default
        if minimum is not None and parsed < minimum:
            self._warn(name, value, f"数值 >= {minimum}", default)
            return default
        return parsed

    def get_bool(
        self,
        key: str,
        default: Optional[bool] = None,
        *,
        aliases: Sequence[str] = (),
    ) -> Optional[bool]:
        """读取布尔配置。兼容 true/false 字符串与 0/1；非法 → 回退 default。"""
        value, name = self._lookup(key, aliases)
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        if isinstance(value, str):
            token = value.strip().lower()
            if token in ("true", "yes", "1", "on"):
                return True
            if token in ("false", "no", "0", "off"):
                return False
        self._warn(name, value, "布尔", default)
        return default

    def get_str(
        self,
        key: str,
        default: Optional[str] = None,
        *,
        aliases: Sequence[str] = (),
        allowed: Optional[Iterable[str]] = None,
    ) -> Optional[str]:
        """读取字符串配置。空串视为未配置；不在 allowed 内 → 回退 default。"""
        value, name = self._lookup(key, aliases)
        if value is None:
            return default
        if not isinstance(value, str):
            self._warn(name, value, "字符串", default)
            return default
        token = value.strip()
        if not token:
            return default
        if allowed is not None and token not in set(allowed):
            self._warn(name, value, f"取值属于 {sorted(set(allowed))}", default)
            return default
        return token

    # -- 语义化快捷读取（三个策略键） ---------------------------------------
    def max_items(self, default: Optional[int]) -> Optional[int]:
        """单次最大采集条数。兼容历史键 ``max_articles``；``<=0`` 视为非法。"""
        return self.get_int("max_items", default, aliases=MAX_ITEMS_ALIASES, minimum=1)

    def filter_mode(self, default: str) -> str:
        """过滤模式：region_only / region_or_topic / topic_only。"""
        return self.get_str("filter_mode", default, allowed=FILTER_MODES) or default

    def keyword_scope(self, default: Optional[str] = None) -> Optional[str]:
        """关键词范围：region / region_topic / topic。None = 不裁剪（旧行为）。"""
        value = self.get_str(
            "keyword_scope",
            default,
            allowed=(*KEYWORD_SCOPES, *KEYWORD_SCOPE_ALIASES),
        )
        return KEYWORD_SCOPE_ALIASES.get(value, value)

    # -- 采集模式（Phase DataSource-National-Mode-3） ----------------------
    def collection_mode(self, default: str = DEFAULT_COLLECTION_MODE) -> str:
        """采集模式：regional / national。

        缺省（未配置 / 非法 / 空串）→ 回退 default（=regional），与历史行为一致。
        旧数据无 collection_mode 即按 regional 解释，**不回填数据库**。
        """
        scope = self.get_str("collection_scope", None, allowed=COLLECTION_SCOPES)
        if scope is not None:
            return scope
        return self.get_str("collection_mode", default, allowed=COLLECTION_MODES) or default

    def collection_scope(self, default: str = DEFAULT_COLLECTION_MODE) -> str:
        """Return the normalized collection scope without mutating config."""

        return self.collection_mode(default)

    def is_national(self, default: str = DEFAULT_COLLECTION_MODE) -> bool:
        """该数据源是否显式声明为全国模式（collection_mode == "national"）。

        作为 National-Mode-4 准入改造的**显式** national 信号，替代
        ``is_national_scope(scope_region_codes)`` 的「空 scope 隐式推断」。
        """
        return self.collection_mode(default) == "national"

    def effective_filter_strategy(
        self,
        default_filter_mode: str = "region_only",
        default_keyword_scope: Optional[str] = None,
    ) -> dict:
        """只读解析「实际生效过滤策略」，供管理端透明化展示。

        返回结构：
            {
              "configured_filter_mode":  配置中显式声明的 filter_mode（未配置为 None）
              "configured_keyword_scope": 配置中显式声明的 keyword_scope（未配置为 None）
              "effective_filter_mode":    实际生效 filter_mode（显式优先，否则采集器默认）
              "effective_keyword_scope":  实际生效 keyword_scope（显式优先，否则采集器默认）
              "source":  "config"（管理员显式配置）/ "collector_default"（采集器默认）
            }

        纯读取：不改变任何采集行为，也不写入数据库。
        """
        cfg_fm = self.get_str("filter_mode", None, allowed=FILTER_MODES)
        cfg_ks = self.keyword_scope()
        configured = cfg_fm is not None or cfg_ks is not None
        effective_fm = cfg_fm if cfg_fm is not None else default_filter_mode
        effective_ks = cfg_ks if cfg_ks is not None else default_keyword_scope
        return {
            "configured_filter_mode": cfg_fm,
            "configured_keyword_scope": cfg_ks,
            "effective_filter_mode": effective_fm,
            "effective_keyword_scope": effective_ks,
            "source": "config" if configured else "collector_default",
        }


# 空配置单例：未经 registry 装配（测试 / 脚本直接实例化采集器）时的默认值，
# 所有读取都会落到调用方 default，即「行为与改造前完全一致」。
EMPTY_CONFIG = DataSourceConfig()


def apply_keyword_scope(
    scope: Optional[str],
    region_kw: Optional[List[str]],
    topic_kw: Optional[List[str]],
) -> Tuple[Optional[List[str]], Optional[List[str]]]:
    """按 keyword_scope 裁剪关键词集合，返回 (region_kw, topic_kw)。

    - ``None``（未配置）：原样返回 —— **保持改造前行为**。
    - ``region``：只保留地域词，主题词置空。
    - ``region_topic``：地域词 + 主题词（等价于原样，语义显式化）。
    - ``topic``：只保留主题词，地域词置空（需配合 filter_mode=topic_only）。

    注意：本函数只做「加载哪些词」的裁剪，**不决定匹配策略**——匹配策略由
    filter_mode 控制。两者可组合，互不隐含。
    """
    scope = KEYWORD_SCOPE_ALIASES.get(scope, scope)
    if scope is None:
        return region_kw, topic_kw
    if scope == "region":
        return region_kw, []
    if scope == "topic":
        return [], topic_kw
    # region_topic：两类词都参与
    return region_kw, topic_kw


def _validate_legacy_collection_config(config: dict) -> dict:
    """校验 ``DataSource.config_json`` 中 collection_mode 的语义组合（National-Mode-3）。

    行为约定
    --------
    - 纯校验：**返回规范化后的 config（不修改 key），非法组合抛 ``ValueError``**。
      **不静默修正**矛盾组合，让调用方（admin API）以明确 422 错误返回。
    - 旧数据无 ``collection_mode`` → 视为 ``regional``（此处不强制写入，读取侧解释）。
    - 本函数只校验「模式语义组合」，不校验具体采集器字段（那是各分支自己的职责）。

    规则
    ----
    - ``collection_mode`` 必须在 ``COLLECTION_MODES`` 内（缺失 → regional）。
    - ``collection_mode == "national"`` 时：
        * ``filter_mode`` 若显式给出，仅允许 ``topic_only``；
        * ``keyword_scope`` 若显式给出，仅允许 ``topic``；
        * 否则（缺省）合法，由读取侧应用默认。
      ⇒ 拒绝如 ``{collection_mode:"national", filter_mode:"region_only"}`` 这类矛盾组合。

    不引用哨兵 code ``"000000"``（National-4 才需要，届时用
    ``app.constants.region.NATIONAL_REGION_CODE``）。
    """
    if not isinstance(config, dict):
        raise ValueError("config_json 必须是 JSON 对象")
    mode = config.get("collection_mode", DEFAULT_COLLECTION_MODE)
    if mode not in COLLECTION_MODES:
        raise ValueError(
            f"collection_mode 取值非法：{mode!r}（允许：{sorted(COLLECTION_MODES)}）"
        )
    if mode == "national":
        fm = config.get("filter_mode")
        if fm is not None and fm not in NATIONAL_FILTER_MODES:
            raise ValueError(
                f"collection_mode=national 时 filter_mode 仅允许 {sorted(NATIONAL_FILTER_MODES)}，"
                f"当前为 {fm!r}（矛盾组合，已拒绝）"
            )
        ks = config.get("keyword_scope")
        normalized_ks = KEYWORD_SCOPE_ALIASES.get(ks, ks)
        if ks is not None and normalized_ks not in NATIONAL_KEYWORD_SCOPES:
            raise ValueError(
                f"collection_mode=national 时 keyword_scope 仅允许 {sorted(NATIONAL_KEYWORD_SCOPES)}，"
                f"当前为 {ks!r}（矛盾组合，已拒绝）"
            )
        return config

    # —— regional / 缺省模式：filter_mode 与 keyword_scope 交叉一致性（Phase Filter-Config-2）——
    # 仅当两者都被显式配置时才交叉校验；单边配置或不配置均放行（读取侧应用默认）。
    fm = config.get("filter_mode")
    ks = config.get("keyword_scope")
    if fm is not None and fm not in FILTER_MODES:
        raise ValueError(
            f"filter_mode 取值非法：{fm!r}（允许：{sorted(FILTER_MODES)}）"
        )
    if ks is not None and ks not in KEYWORD_SCOPES:
        raise ValueError(
            f"keyword_scope 取值非法：{ks!r}（允许：{sorted(KEYWORD_SCOPES)}）"
        )
    if fm == "region_only" and ks == "topic":
        raise ValueError(
            "filter_mode=region_only 与 keyword_scope=topic 矛盾"
            "（仅地域过滤不应使用纯主题词范围），已拒绝"
        )
    if fm == "topic_only" and ks == "region":
        raise ValueError(
            "filter_mode=topic_only 与 keyword_scope=region 矛盾"
            "（纯主题过滤不应使用纯地域词范围），已拒绝"
        )
    return config


# MediaCrawler-2A contract override.  Kept at module scope so older callers
# retain the same import while the validator now understands collection_scope.
def validate_data_source_config(config: dict) -> dict:
    if not isinstance(config, dict):
        raise ValueError("config_json must be a JSON object")

    unknown = sorted(set(config) - MEDIACRAWLER_CONFIG_KEYS)
    if unknown:
        raise ValueError(
            "MediaCrawler config contains unsupported top-level keys: "
            + ", ".join(unknown)
        )
    forbidden = sorted(set(config) & FORBIDDEN_MEDIACRAWLER_CONFIG_KEYS)
    if forbidden:
        raise ValueError(
            "MediaCrawler config must not contain runtime or credential keys: "
            + ", ".join(forbidden)
        )

    scope = config.get("collection_scope")
    legacy_mode = config.get("collection_mode")
    if scope is not None and scope not in COLLECTION_SCOPES:
        raise ValueError(f"collection_scope must be one of {sorted(COLLECTION_SCOPES)}")
    if legacy_mode is not None and legacy_mode not in COLLECTION_MODES:
        raise ValueError(f"collection_mode must be one of {sorted(COLLECTION_MODES)}")
    if scope is not None and legacy_mode is not None and scope != legacy_mode:
        raise ValueError("collection_scope and collection_mode must match")
    mode = scope or legacy_mode or DEFAULT_COLLECTION_MODE

    if "collector" in config and config["collector"] != "mediacrawler":
        raise ValueError("collector must be 'mediacrawler'")
    platform = get_mediacrawler_platform_spec(config.get("platform"))
    if "schema_version" in config and config["schema_version"] != 1:
        raise ValueError("schema_version must be 1")
    if "crawler_type" in config:
        platform.validate_crawler_type(config["crawler_type"])
    if "login_type" in config:
        platform.validate_login_type(config["login_type"])
    if "keywords" in config:
        keywords = config["keywords"]
        if not isinstance(keywords, list) or any(
            not isinstance(item, str) or not item.strip() for item in keywords
        ):
            raise ValueError("keywords must be a list of non-empty strings")
    if "max_items" in config:
        max_items = config["max_items"]
        if (
            isinstance(max_items, bool)
            or not isinstance(max_items, int)
            or not 1 <= max_items <= 20
        ):
            raise ValueError("max_items must be between 1 and 20")
    for key in ("get_comment", "get_sub_comment"):
        if key in config and not isinstance(config[key], bool):
            raise ValueError(f"{key} must be boolean")
    if "content_type" in config and (
        not isinstance(config["content_type"], str) or not config["content_type"].strip()
    ):
        raise ValueError("content_type must be a non-empty string")
    if "comments" in config:
        comments = config["comments"]
        if not isinstance(comments, dict):
            raise ValueError("comments must be an object")
        unknown_comments = sorted(set(comments) - {"enabled", "sub_comments"})
        if unknown_comments:
            raise ValueError(
                "comments contains unsupported keys: " + ", ".join(unknown_comments)
            )
        if any(
            key in comments and not isinstance(comments[key], bool)
            for key in ("enabled", "sub_comments")
        ):
            raise ValueError("comments.enabled and comments.sub_comments must be boolean")
    if "platform_options" in config and not isinstance(config["platform_options"], dict):
        raise ValueError("platform_options must be an object")

    if mode == "national":
        fm = config.get("filter_mode")
        if fm is not None and fm not in FILTER_MODES:
            raise ValueError(f"filter_mode must be one of {sorted(FILTER_MODES)}")
        ks = config.get("keyword_scope")
        allowed_scopes = (*KEYWORD_SCOPES, *KEYWORD_SCOPE_ALIASES)
        if ks is not None and ks not in allowed_scopes:
            raise ValueError(f"keyword_scope must be one of {sorted(allowed_scopes)}")
        normalized_ks = KEYWORD_SCOPE_ALIASES.get(ks, ks)
        if fm == "region_only" and normalized_ks == "topic":
            raise ValueError("filter_mode=region_only conflicts with keyword_scope=topic")
        if fm == "topic_only" and normalized_ks == "region":
            raise ValueError("filter_mode=topic_only conflicts with keyword_scope=region")
        return config

    fm = config.get("filter_mode")
    ks = config.get("keyword_scope")
    if fm is not None and fm not in FILTER_MODES:
        raise ValueError(f"filter_mode must be one of {sorted(FILTER_MODES)}")
    allowed_scopes = (*KEYWORD_SCOPES, *KEYWORD_SCOPE_ALIASES)
    if ks is not None and ks not in allowed_scopes:
        raise ValueError(f"keyword_scope must be one of {sorted(allowed_scopes)}")
    normalized_ks = KEYWORD_SCOPE_ALIASES.get(ks, ks)
    if fm == "region_only" and normalized_ks == "topic":
        raise ValueError("filter_mode=region_only conflicts with keyword_scope=topic")
    if fm == "topic_only" and normalized_ks == "region":
        raise ValueError("filter_mode=topic_only conflicts with keyword_scope=region")
    return config


def validate_mediacrawler_region_contract(
    config: dict, scope_region_codes: str | Iterable[str] | None
) -> dict:
    """Validate the source scope contract.

    An empty ``scope_region_codes`` means national collection.  Both Weibo and
    Xiaohongshu may use that mode because their business coverage can change;
    regional scope remains available through the admin configuration screen.
    """

    mode = (
        config.get("collection_scope")
        or config.get("collection_mode")
        or DEFAULT_COLLECTION_MODE
    )
    if mode == "national" and isinstance(scope_region_codes, str):
        if any(part.strip() for part in scope_region_codes.split(",")):
            raise ValueError(
                "collection_mode=national requires empty scope_region_codes"
            )
    elif mode == "national" and scope_region_codes:
        raise ValueError(
            "collection_mode=national requires empty scope_region_codes"
        )
    validate_data_source_config(config)
    if config.get("platform") != "weibo":
        return config
    if mode == "national":
        return config
    if mode != "regional":
        raise ValueError(
            "weibo_mediacrawler 必须使用 collection_scope=regional，禁止 national"
        )
    if isinstance(scope_region_codes, str):
        codes = [part.strip() for part in scope_region_codes.split(",") if part.strip()]
    else:
        codes = [str(part).strip() for part in (scope_region_codes or []) if str(part).strip()]
    if not codes:
        raise ValueError(
            "weibo_mediacrawler 必须使用 scope_region_codes=131000（廊坊全域）"
        )
    return config
