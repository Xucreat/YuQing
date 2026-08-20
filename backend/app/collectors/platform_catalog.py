"""平台目录与平台冲突校验（轻量共享模块，无新增表 / 状态机 / 服务）。

用途：在 bb-browser 聚合采集（BBBrowserCollector）与 MediaCrawler 之间，
对「同一平台不得被两个 enabled=true 的数据源同时采集」做统一裁决。

设计约束（与本期需求一致）：
- 不新增数据库表 / 迁移。
- 平台归属完全由 data_sources 表动态计算（enabled + config_json）。
- enabled=false 不占用平台；schedule_enabled 不影响占用判断。
- 仅做平台选择与冲突校验，不做 partial success / 重试 / 熔断。
- 冲突校验框架对 weibo/xiaohongshu/zhihu 同样有效（即使当前 bb-browser 暂未开放），
  以保证未来可切换时不漏判。
"""
from __future__ import annotations

from dataclasses import dataclass

# 与 admin_data_sources._is_external_browser 精确对齐的 class_path
BB_BROWSER_CLASS_PATH = "app.collectors.bb_browser_collector.BBBrowserCollector"

# 平台别名 -> 规范 key。未来若 bb-browser 采用 m_weibo / xhs 别名，也能正确比对冲突。
PLATFORM_ALIASES: dict[str, str] = {
    "m_weibo": "weibo",
    "xhs": "xiaohongshu",
}


@dataclass(frozen=True)
class PlatformDef:
    key: str
    name: str
    # 支持的采集器类型集合：bb_browser / mediacrawler
    collectors: tuple[str, ...]
    source_type: str
    # bb-browser Python 侧是否已具备完整采集 + 归一化能力（False = 暂未开放）
    python_normalized: bool
    collect_type: str  # search / hot / question


# 平台目录（稳定顺序；新增平台只需在此追加一条）。
PLATFORM_CATALOG: list[PlatformDef] = [
    PlatformDef("baidu", "百度", ("bb_browser",), "baidu_result", True, "search"),
    PlatformDef("hupu", "虎扑", ("bb_browser",), "hupu_post", True, "hot"),
    PlatformDef("toutiao", "今日头条", ("bb_browser",), "toutiao_item", True, "hot"),
    PlatformDef("bilibili", "B站", ("bb_browser",), "bilibili_video", True, "search"),
    PlatformDef("youtube", "YouTube", ("bb_browser",), "youtube_video", True, "search"),
    PlatformDef("weibo", "微博", ("mediacrawler", "bb_browser"), "weibo_post", False, "search"),
    PlatformDef("xiaohongshu", "小红书", ("mediacrawler", "bb_browser"), "xiaohongshu_bb", True, "search"),
    PlatformDef("zhihu", "知乎", ("bb_browser",), "zhihu_bb", True, "question"),
]


def canonical_platform(key: str) -> str:
    """平台 key 归一化为规范 key（处理别名，小写，去空白）。"""
    if not key:
        return ""
    k = str(key).strip().lower()
    return PLATFORM_ALIASES.get(k, k)


def platform_by_key(key: str) -> PlatformDef | None:
    ck = canonical_platform(key)
    for p in PLATFORM_CATALOG:
        if p.key == ck:
            return p
    return None


def bb_browser_selectable_platforms() -> set[str]:
    """bb-browser 当前可在前端勾选的平台（Python 已完成归一化）。"""
    return {p.key for p in PLATFORM_CATALOG if p.python_normalized and "bb_browser" in p.collectors}


def _class_kind(class_path: str) -> str:
    """按 class_path 判定采集器类型：bb_browser / mediacrawler / other。"""
    cp = class_path or ""
    if cp == BB_BROWSER_CLASS_PATH:
        return "bb_browser"
    if "mediacrawler" in cp.lower():
        return "mediacrawler"
    return "other"


def compute_owned_platforms(
    class_path: str, config_json: dict, enabled: bool
) -> set[str]:
    """返回该数据源在 enabled 时占用的规范平台 key 集合；enabled=False 返回空集。

    - MediaCrawler：从 config_json.platform 读取（enabled 时占用）。
    - bb_browser：从 config_json.platforms 数组读取（enabled 时数组内均占用）。
    - 其它采集器：不占用平台（空集）。
    """
    if not enabled:
        return set()
    cfg = config_json or {}
    kind = _class_kind(class_path)
    if kind == "mediacrawler":
        plat = cfg.get("platform")
        if plat:
            return {canonical_platform(str(plat))}
        return set()
    if kind == "bb_browser":
        plats = cfg.get("platforms") or []
        return {canonical_platform(str(p)) for p in plats if p}
    return set()


@dataclass
class PlatformConflict:
    platform: str
    platform_name: str
    self_class_path: str
    self_name: str
    owner_class_path: str
    owner_name: str
    message: str


def detect_platform_conflict(
    self_class_path: str,
    self_enabled: bool,
    self_config: dict,
    self_name: str,
    other_sources: list,  # list of (id, name, class_path, enabled, config_json)
) -> PlatformConflict | None:
    """检测 self 与已启用 other_sources 之间的平台占用冲突。

    other_sources: [(id, name, class_path, enabled, config_json), ...]
    返回首个冲突；无冲突返回 None。
    """
    self_plats = compute_owned_platforms(self_class_path, self_config, self_enabled)
    if not self_plats:
        return None
    for (_oid, oname, ocp, oen, ocfg) in other_sources:
        other_plats = compute_owned_platforms(ocp, ocfg, oen)
        overlap = self_plats & other_plats
        if overlap:
            plat = sorted(overlap)[0]
            pdef = platform_by_key(plat)
            pname = pdef.name if pdef else plat
            self_kind = _class_kind(self_class_path)
            owner_kind = _class_kind(ocp)
            if self_kind == "bb_browser" and owner_kind == "mediacrawler":
                msg = (
                    f"{pname}已由「{oname}」数据源启用，当前不允许 bb-browser 同时采集{pname}。"
                    f"若要改用 bb-browser，请先停用「{oname}」数据源。"
                )
            elif self_kind == "mediacrawler" and owner_kind == "bb_browser":
                msg = (
                    f"{pname}已由「{oname}」数据源启用，当前不允许 MediaCrawler 同时采集{pname}。"
                    f"若要改用 MediaCrawler，请先取消「{oname}」中的{pname}平台选择。"
                )
            else:
                msg = (
                    f"{pname}已由「{oname}」数据源启用，不允许被「{self_name}」同时启用。"
                    f"请先停用「{oname}」。"
                )
            return PlatformConflict(
                platform=plat,
                platform_name=pname,
                self_class_path=self_class_path,
                self_name=self_name,
                owner_class_path=ocp,
                owner_name=oname,
                message=msg,
            )
    return None


def dedupe_platforms(platforms) -> list[str]:
    """平台去重并保持稳定顺序（按首次出现顺序）。同时归一化别名。"""
    seen: set[str] = set()
    out: list[str] = []
    for p in platforms or []:
        cp = canonical_platform(str(p))
        if cp and cp not in seen:
            seen.add(cp)
            out.append(cp)
    return out
