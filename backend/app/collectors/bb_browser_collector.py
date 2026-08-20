"""bb-browser 聚合型数据源采集器（Phase 1B 可靠性修复 + 管理端接入）。

设计目标
--------
在不修改 MediaCrawler、不修改现有微博/小红书链路、不触碰历史交换目录、
不杀/重启任何进程的前提下，为 YQ 新增一个独立的聚合型 data_source：

    bb-browser 聚合采集

它通过「当前已经验证的」bb-browser worker（collector_exchange_runtime）来采集
以下平台：baidu / hupu / toutiao / bilibili / youtube。
（zhihu 当前 C:\\cdp-profile 未登录 → 401，本阶段排除；
  m_weibo / xiaohongshu 仍由 MediaCrawler 负责，禁止接入。）

工作方式（与已验证 worker 严格对齐）
--------------------------------------
1. fetch() 把本次任务写成一个 manifest 文件，原子 rename 到
   control_root/outgoing/，文件名唯一（manifest_id）。
2. 让「正在运行的」collector_exchange worker（PID 15652）去消费该 manifest：
   它对每个 rule 的 sources 调 bb-browser CLI，把结构化结果写到
   exchange_root/incoming/{source}_{uuid}.txt，文件头含
   ``task_manifest_id=<manifest_id>``、``task_id=<rule_id>``、``source_key=<platform>``。
3. fetch() 只读取「命中本次 manifest_id」的 incoming 文件（按
   task_manifest_id + task_id + source_key 精确匹配），绝不消费历史文件。
4. 解析每个 incoming 文件，拆成「逐条」标准化 Opinion dict（不整段塞 content）。
5. 返回标准化列表；由 CollectorService 去重 / 建 Opinion / AI 分析。
6. 仅当 CollectorService 完成入库与分析后，通过 ack_pending_export()
   把本次 incoming 文件移动到 exchange_root/processed（幂等、可恢复）。

Phase 1B 修复要点
-----------------
- 多关键词：同一平台多个关键词 → 多个 task_id 文件。改用 list[PendingFile]
  （含 manifest_id/task_id/source_key/path/file_size/collected_at），按
  (task_id, source_key) 精确匹配，不再按 source_key 单一覆盖。
- external_id：禁止 *:none。回退顺序 原生ID → 规范化URL哈希 →
  platform+title+content+author 内容哈希；title+content 均空则跳过该条。
- ack：幂等可恢复。移动前校验源存在、目标不存在或内容一致；中途失败回滚；
  目标已存在且内容一致视为已确认；绝不部分清空 _pending_files。
- outgoing 并发：发现 outgoing 中已有其它未处理 .txt → 直接失败（Plan A），
  不写入新 manifest，交由下一轮重试。

重要约束遵循
------------
- 禁止直接调用 Node CLI 绕过 worker（manifest 交给 worker 执行）。
- 禁止直写 Opinion（仅返回 dict，由 CollectorService 入库）。
- 禁止消费旧 incoming / landing-8platform / collector_exchange 旧交换根。
- 禁止把任意 config_json 当 shell 参数透传（平台命令使用服务端白名单）。
"""
from __future__ import annotations

import datetime
import hashlib
import json
import logging
import os
import re
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, List, Optional, Tuple

from app.collectors.base import BaseCollector
from app.collectors.source_config import DataSourceConfig
from app.collectors.bb_browser_runtime import (
    CollectorError,
    OutgoingLockError,
    OutgoingMutex,
    classify_adapter_error,
    verify_runtime_lock,
    ERR_ADAPTER_ERROR,
    ERR_EMPTY_RESULT,
    ERR_LOGIN_REQUIRED,
    ERR_RUNTIME_DRIFT,
    ERR_TIMEOUT,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 平台白名单（Phase 1A/1B 允许采集的平台）
# ---------------------------------------------------------------------------
SEARCH_PLATFORMS = ("baidu", "bilibili", "youtube")   # 按关键词采集
HOT_PLATFORMS = ("hupu", "toutiao")                    # 热榜型，不消耗关键词

# 服务端平台白名单：fetch() 只会把命中本集合的平台写进 manifest 的 sources=。
# 任何 weibo / xiaohongshu / zhihu / 未知平台都会被强制剔除（不允许经 shell 透传）。
ALLOWED_PLATFORMS = SEARCH_PLATFORMS + HOT_PLATFORMS

# 管理端校验显式拒绝的平台（白名单补集）。
REJECTED_PLATFORMS = {
    "weibo", "m_weibo", "xiaohongshu", "xhs", "zhihu",
}

# 平台展示元数据（source / source_type 必须稳定，供去重与前端展示）
PLATFORM_META = {
    "baidu":     {"source": "百度",     "source_type": "baidu_result",   "array": "results", "kind": "search"},
    "bilibili":  {"source": "B站",       "source_type": "bilibili_video", "array": "videos",  "kind": "search"},
    "youtube":   {"source": "YouTube",   "source_type": "youtube_video", "array": "videos",  "kind": "search"},
    "hupu":      {"source": "虎扑",      "source_type": "hupu_post",     "array": "items",   "kind": "hot"},
    "toutiao":   {"source": "今日头条",  "source_type": "toutiao_item",  "array": "items",   "kind": "hot"},
}

DEFAULT_PLATFORMS = list(ALLOWED_PLATFORMS)

RECORD_VERSION = 1
MANIFEST_VERSION = 2

# incoming 记录文件头部标记（worker 写入，fetch() 据此过滤本次任务文件）
HEADER_TASK_MANIFEST_ID = "task_manifest_id"
HEADER_SOURCE_KEY = "source_key"
HEADER_TASK_ID = "task_id"
CONTENT_BEGIN = "---BEGIN CONTENT---"
CONTENT_END = "---END CONTENT---"


@dataclass
class PendingFile:
    """一次采集任务对应的一个 incoming 结果文件。

    一个平台在多个关键词下会生成多个 task_id 文件，因此不再用
    dict[source_key, Path]（会互相覆盖），而是用列表 + 精确身份标识。
    """

    manifest_id: str
    task_id: str
    source_key: str
    path: Path
    file_size: int = 0
    collected_at: Optional[float] = None


# ===========================================================================
# 纯函数：URL / external_id 工具
# ===========================================================================
def normalize_url(url: Optional[str]) -> str:
    """规范化 URL 用于哈希：去空白、转小写、去尾斜杠。

    保留 query（百度跳转链接的 query 是链接一部分，稳定）。
    """
    if not url:
        return ""
    s = str(url).strip().lower()
    if s.endswith("/"):
        s = s[:-1]
    return s


def url_hash(url: Optional[str], prefix: str, width: int = 16) -> str:
    """返回 ``prefix:<sha256[:width]>`` 的稳定外部 ID（要求 url 非空）。"""
    norm = normalize_url(url)
    if not norm:
        raise ValueError("url_hash 需要非空 url")
    digest = hashlib.sha256(norm.encode("utf-8")).hexdigest()
    return f"{prefix}:{digest[:width]}"


def extract_digits(path_like: str, prefix: str) -> Optional[str]:
    """从 URL/路径中提取一串数字作为平台原生 ID 兜底（3 位起）。"""
    if not path_like:
        return None
    nums = re.findall(r"(\d{3,})", str(path_like))
    if not nums:
        return None
    return f"{prefix}:{max(nums, key=len)}"


def _native_id(platform: str, item: dict, url: Optional[str]) -> Optional[str]:
    """平台原生稳定 ID（优先），无则返回 None。

    baidu 无原生 ID；hupu 用 tid；toutiao 用 trending/a id；
    bilibili 用 bvid；youtube 用 videoId。"""
    if platform == "baidu":
        return None
    if platform == "hupu":
        tid = (item.get("tid") or "").strip()
        if tid:
            return f"hupu:{tid}"
        return None
    if platform == "toutiao":
        m = re.search(r"/(?:trending|a)/(\d+)", str(url or ""))
        if m:
            return f"toutiao:{m.group(1)}"
        return None
    if platform == "bilibili":
        bvid = (item.get("bvid") or "").strip()
        if bvid:
            return f"bilibili:{bvid}"
        return None
    if platform == "youtube":
        vid = (item.get("videoId") or item.get("video_id") or "").strip()
        if vid:
            return f"youtube:{vid}"
        return None
    return None


def _content_hash_id(platform: str, item: dict) -> Optional[str]:
    """内容哈希回退：platform + 标题 + 正文 + 作者。

    title+content 同时为空 → 返回 None（调用方跳过该条，绝不生成 *:none）。
    """
    title = (item.get("title") or "").strip()
    content = (
        item.get("snippet")
        or item.get("description")
        or item.get("content")
        or title
        or ""
    ).strip()
    author = (item.get("author") or item.get("channel") or "").strip()
    if not (title or content):
        return None
    raw = f"{platform}\n{title}\n{content}\n{author}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return f"{platform}:{digest[:16]}"


def stable_external_id(platform: str, item: dict, url: Optional[str]) -> Optional[str]:
    """生成稳定的外部 ID（去重核心）。

    回退顺序（严禁 *:none）：
      1. 平台原生 ID（tid / bvid / videoId / trending id）
      2. 规范化 URL 哈希
      3. platform + title + content + author 内容哈希
    三者皆不可得（title+content 空）→ 返回 None（上层跳过该条）。
    """
    native = _native_id(platform, item, url)
    if native:
        return native
    norm = normalize_url(url)
    if norm:
        return url_hash(url, platform)
    return _content_hash_id(platform, item)


def parse_pub_time(value: Any) -> Optional[datetime.datetime]:
    """尽量可靠地解析发布时间。

    - YouTube 的 publishedTime 是「9小时前」这类相对描述 → None（不可靠）。
    - B站 pub_date 是 ISO（如 2025-11-28T10:20:16.000Z）→ 解析为 naive UTC。
    - 其它无法可靠解析的 → None。
    """
    if not value or not str(value).strip():
        return None
    s = str(value).strip()
    if re.search(r"[\u4e00-\u9fff]", s) and any(k in s for k in ("前", "分钟", "小时", "天", "周", "月", "年")):
        return None
    try:
        txt = s.replace("Z", "+00:00")
        dt = datetime.datetime.fromisoformat(txt)
        if dt.tzinfo is not None:
            dt = dt.astimezone(datetime.timezone.utc).replace(tzinfo=None)
        return dt
    except (ValueError, TypeError):
        return None


# ===========================================================================
# 纯函数：incoming 记录解析 + 逐条归一化
# ===========================================================================
def parse_record_text(text: str) -> dict:
    """解析 worker 产出的 incoming 记录文本。

    返回：
        {
          "header": {task_manifest_id, task_id, source_key, source_name, record_id, ...},
          "content": <解析后的 JSON 对象 或 None>,
          "error":  <adapter 错误对象 或 None>,
          "raw_content": <CONTENT 块原文>,
        }
    解析失败或缺失 CONTENT 块时 content=None 且不抛异常（由上层决策）。
    """
    header: dict[str, str] = {}
    for line in text.splitlines():
        if "=" in line:
            k, _, v = line.partition("=")
            k = k.strip()
            if k and not k.startswith("-") and not k.startswith(CONTENT_BEGIN[:3]):
                header[k] = v.strip()
    content = None
    error = None
    raw_content = ""
    m = re.search(
        re.escape(CONTENT_BEGIN) + r"\n(.*?)\n" + re.escape(CONTENT_END),
        text,
        re.S,
    )
    if m:
        raw_content = m.group(1)
        try:
            parsed = json.loads(raw_content)
            if isinstance(parsed, dict) and parsed.get("error") and not parsed.get("result"):
                error = parsed
            else:
                content = parsed
        except json.JSONDecodeError:
            content = None
    return {
        "header": header,
        "content": content,
        "error": error,
        "raw_content": raw_content,
    }


def parse_header(text: str) -> dict:
    """仅解析头部 key=value（含 task_manifest_id / task_id / source_key）。"""
    header: dict[str, str] = {}
    for line in text.splitlines():
        if "=" in line:
            k, _, v = line.partition("=")
            k = k.strip()
            if k and not k.startswith("-") and not k.startswith(CONTENT_BEGIN[:3]):
                header[k] = v.strip()
    return header


def unwrap_result(data: Any) -> Tuple[Optional[list], Optional[str]]:
    """从 adapter 返回的 JSON 中取出条目数组。

    兼容三种形态：
      1. 外层 {"result": {...}}               （bb-browser 标准）
      2. 直接返回 {...}（result 平铺）          （部分 adapter 直接返回）
      3. 直接返回 [...]                         （极少）
    返回 (items, array_key)。找不到数组时 (None, None)。
    """
    if isinstance(data, list):
        return data, None
    if not isinstance(data, dict):
        return None, None
    res = data.get("result")
    if isinstance(res, list):
        return res, "result"
    if isinstance(res, dict):
        for key in ("results", "items", "videos", "data", "list", "posts", "news"):
            arr = res.get(key)
            if isinstance(arr, list):
                return arr, key
        return [], None
    for key in ("results", "items", "videos", "data", "list", "posts", "news"):
        arr = data.get(key)
        if isinstance(arr, list):
            return arr, key
    return None, None


def raw_item_count(platform: str, content: Any) -> int:
    """上游 adapter 实际返回的原始条目数（截断前的口径）。"""
    if not isinstance(content, dict):
        return 0
    items, _ = unwrap_result(content)
    return len(items or [])


def normalize_item(platform: str, item: dict) -> Optional[dict]:
    """把单个平台条目归一化为标准 Opinion dict；无有效 external_id 时返回 None。"""
    meta = PLATFORM_META[platform]
    source = meta["source"]
    source_type = meta["source_type"]
    url = (item.get("url") or "").strip() or None

    if platform == "baidu":
        title = (item.get("title") or "").strip()
        content = (item.get("snippet") or title or "").strip()
        external_id = stable_external_id(platform, item, url)
        pub = None
        engagement: dict = {}
        author = None
    elif platform == "hupu":
        title = (item.get("title") or "").strip()
        content = title
        external_id = stable_external_id(platform, item, url)
        pub = parse_pub_time(item.get("pub_date"))
        engagement = {"lights": item.get("lights"), "comments": item.get("replies")}
        author = None
    elif platform == "toutiao":
        title = (item.get("title") or "").strip()
        content = title
        external_id = stable_external_id(platform, item, url)
        pub = parse_pub_time(item.get("publish_time") or item.get("pubDate"))
        engagement = {"hot_value": item.get("hot_value")}
        author = None
    elif platform == "bilibili":
        title = (item.get("title") or "").strip()
        content = (item.get("description") or title or "").strip()
        external_id = stable_external_id(platform, item, url)
        pub = parse_pub_time(item.get("pub_date"))
        engagement = {
            "play": item.get("play"),
            "danmaku": item.get("danmaku"),
            "likes": item.get("like"),
            "favorites": item.get("favorites"),
        }
        author = (item.get("author") or "").strip() or None
    elif platform == "youtube":
        title = (item.get("title") or "").strip()
        content = (item.get("description") or title or "").strip()
        external_id = stable_external_id(platform, item, url)
        pub = parse_pub_time(item.get("publishedTime"))
        engagement = {"views": item.get("views")}
        author = (item.get("channel") or "").strip() or None
    else:
        title = str(item.get("title") or item.get("text") or "")
        content = str(item.get("content") or title)
        external_id = stable_external_id(platform, item, url)
        pub = None
        engagement = {}
        author = None

    # 无有效 external_id → 跳过该条（绝不生成 *:none）
    if not external_id:
        logger.warning(
            "归一化跳过无效条目 platform=%s title=%r（无法生成稳定 external_id）",
            platform, (item.get("title") or "")[:40],
        )
        return None

    return {
        "title": title,
        "content": content,
        "source": source,
        "source_type": source_type,
        "url": url or "",
        "external_id": external_id,
        "author": author,
        "publish_time": pub,
        "engagement": engagement,
    }


def normalize_record(platform: str, content: Any, max_items: Optional[int] = None) -> list:
    """把一个 incoming 文件的内容 JSON 拆成逐条标准化 Opinion dict 列表。

    - content 为 None / 非 dict / 含 error → 返回 []（不抛异常，交由上层判断是否失败）。
    - 按平台 array key 取出条目数组，逐条 normalize_item（无有效 external_id 的被跳过）。
    - max_items 限制最终返回条数（不足则全部保留；这是「截断后」的 returned 口径）。
    """
    if platform not in PLATFORM_META:
        return []
    if not isinstance(content, dict):
        return []
    if content.get("error") and not content.get("result"):
        return []
    items, _ = unwrap_result(content)
    if not items:
        return []
    out = [normalize_item(platform, it) for it in items if isinstance(it, dict)]
    out = [o for o in out if o is not None]
    if max_items is not None and max_items >= 0:
        out = out[:max_items]
    return out


# ===========================================================================
# 纯函数：manifest 生成 + 规则解析
# ===========================================================================
def build_manifest(
    manifest_id: str,
    keywords: Iterable[str],
    platforms: Iterable[str],
    *,
    keyword_config_version: str = "1",
    policy_version: str = "1",
    exported_at: Optional[str] = None,
) -> str:
    """生成 worker 可消费的 manifest 文本。

    规则约定（与已验证 worker 严格对齐）：
    - 每个关键词生成一条 search 规则（sources=搜索型平台）。
    - 热榜型平台只生成一条 hot 规则（sources=热榜型平台，match_terms 占位）。
    - rule_id 必须包含 ``-rule-`` 片段，因为 worker 用
      ``rule_id.rsplit('-rule-', 1)[0]`` 推导 task_manifest_id。
      因此 hot 规则也用 ``<manifest_id>-rule-hot-0001`` 而非 ``-hot-``。

    返回纯文本（含 RULE_VERSION / rule_manifest_id 等审计头）。
    """
    platforms = [p for p in platforms if p in ALLOWED_PLATFORMS]
    search_plats = [p for p in platforms if PLATFORM_META[p]["kind"] == "search"]
    hot_plats = [p for p in platforms if PLATFORM_META[p]["kind"] == "hot"]
    if not platforms:
        raise ValueError("manifest 至少需要一个允许的平台")
    if search_plats and not keywords:
        raise ValueError("搜索型平台必须有至少一个关键词，否则无法生成 rule")

    exported_at = exported_at or datetime.datetime.now(
        datetime.timezone.utc
    ).strftime("%Y-%m-%dT%H:%M:%SZ")

    lines: list[str] = []
    lines.append(f"RULE_VERSION={MANIFEST_VERSION}")
    lines.append(f"rule_manifest_id={manifest_id}")
    lines.append(f"exported_at={exported_at}")
    lines.append(f"keyword_config_version={keyword_config_version}")
    lines.append(f"policy_version={policy_version}")
    lines.append("")

    for i, kw in enumerate(keywords, start=1):
        kw = str(kw).strip()
        if not kw:
            continue
        lines.append("---BEGIN RULE---")
        lines.append(f"rule_id={manifest_id}-rule-{i:04d}")
        lines.append("rule_action=collect")
        lines.append(f"match_terms={kw}")
        lines.append(f"sources={','.join(search_plats)}")
        lines.append("---END RULE---")
        lines.append("")

    if hot_plats:
        lines.append("---BEGIN RULE---")
        lines.append(f"rule_id={manifest_id}-rule-hot-0001")
        lines.append("rule_action=collect")
        lines.append("match_terms=__bb_browser_hot__")
        lines.append(f"sources={','.join(hot_plats)}")
        lines.append("---END RULE---")
        lines.append("")

    return "\n".join(lines)


def parse_manifest_rules(manifest_text: str) -> List[Tuple[str, List[str]]]:
    """从 manifest 文本解析规则 → [(rule_id, [source_keys]), ...]。"""
    rules: List[Tuple[str, List[str]]] = []
    cur_id: Optional[str] = None
    cur_src: Optional[str] = None
    in_rule = False
    for line in manifest_text.splitlines():
        s = line.strip()
        if s == "---BEGIN RULE---":
            in_rule = True
            cur_id = None
            cur_src = None
        elif s == "---END RULE---":
            if cur_id and cur_src:
                rules.append((cur_id, [x.strip() for x in cur_src.split(",") if x.strip()]))
            in_rule = False
        elif in_rule:
            if s.startswith("rule_id="):
                cur_id = s.split("=", 1)[1].strip()
            elif s.startswith("sources="):
                cur_src = s.split("=", 1)[1].strip()
    return rules


def expected_tasks_for_manifest(manifest_text: str) -> List[Tuple[str, str]]:
    """根据 manifest 实际生成的 rule_id 计算期望任务集合。

    返回 [(task_id, source_key), ...]。3 关键词 × 3 搜索平台 + 1 热榜(hupu,toutiao)
    → 11 个任务。
    """
    out: List[Tuple[str, str]] = []
    for rule_id, sources in parse_manifest_rules(manifest_text):
        for src in sources:
            out.append((rule_id, src))
    return out


def write_manifest_atomic(outgoing_dir: str | Path, manifest_id: str, text: str) -> Path:
    """把 manifest 先写临时文件再原子 rename，避免 worker 读取半文件。"""
    outgoing = Path(outgoing_dir)
    outgoing.mkdir(parents=True, exist_ok=True)
    target = outgoing / f"{manifest_id}.txt"
    tmp = outgoing / f".{manifest_id}.tmp"
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, target)  # 同文件系统原子
    return target


# ===========================================================================
# Collector
# ===========================================================================
class BBBrowserCollector(BaseCollector):
    """bb-browser 聚合采集器（独立 data_source，复用已验证 worker）。"""

    source_name = "bb-browser聚合采集"

    def __init__(
        self,
        *,
        platforms: Optional[list[str]] = None,
        control_root: Optional[str] = None,
        exchange_root: Optional[str] = None,
        bb_browser_cli: Optional[str] = None,
        cdp_url: Optional[str] = None,
        daemon_url: Optional[str] = None,
        timeout_seconds: int = 240,
        poll_interval_seconds: int = 2,
        max_items_per_platform: int = 20,
        manifest_version: int = MANIFEST_VERSION,
        allow_weibo: bool = False,
        allow_xiaohongshu: bool = False,
        collection_mode: str = "regional",
        test_mode: bool = False,
        **kwargs,
    ) -> None:
        # 平台白名单：强制收敛到服务端允许集合，剔除任何 weibo/xhs/zhihu/未知。
        requested = list(platforms or DEFAULT_PLATFORMS)
        self.platforms = [p for p in requested if p in ALLOWED_PLATFORMS]
        if not allow_weibo:
            self.platforms = [p for p in self.platforms if p != "m_weibo" and p != "weibo"]
        if not allow_xiaohongshu:
            self.platforms = [
                p for p in self.platforms if p != "xiaohongshu" and p != "xhs"
            ]
        # 双保险：显式拒绝列表
        self.platforms = [p for p in self.platforms if p not in REJECTED_PLATFORMS]

        self.control_root = Path(control_root) if control_root else None
        self.exchange_root = Path(exchange_root) if exchange_root else None
        self.bb_browser_cli = bb_browser_cli
        self.cdp_url = cdp_url
        self.daemon_url = daemon_url
        self.timeout_seconds = int(timeout_seconds)
        self.poll_interval_seconds = int(poll_interval_seconds)
        self.max_items_per_platform = int(max_items_per_platform)
        self.manifest_version = int(manifest_version)
        self.collection_mode = collection_mode

        # §八 fail-open 控制：测试环境显式 test_mode=True 时缺失 lock 不阻断；
        # 生产环境（默认 test_mode=False）缺失 lock 必须失败（runtime_drift）。
        # 也可经环境变量 BBBROWSER_TEST_MODE=1 全局开启（仅测试用）。
        self._test_mode = bool(test_mode) or bool(os.environ.get("BBBROWSER_TEST_MODE"))
        self.scope_region_codes = None
        self.source_config = DataSourceConfig(
            {"collection_mode": self.collection_mode, "platforms": self.platforms}
        )

        # 运行状态（CollectorService 会读取这些属性写 CollectorRun）
        self.last_fetched_raw: int = 0          # 上游原始条数（截断前）
        self.normalized_count: int = 0           # 归一化后（截断前）
        self.last_not_exported_returned: int = 0  # fetch 实际返回（截断后 = len(items)）
        self.last_comments_seen: int = 0
        self.last_comments_skipped: int = 0

        # 本次 fetch 产生的、待 ack 的 incoming 文件
        self._pending_files: list[Path] = []
        self._current_manifest_id: Optional[str] = None
        self._mutex = None  # 跨进程互斥锁（§三），fetch 期间持有

        # §八：运行时锁 preflight 路径（control_root 的父目录 / phase2_runtime_lock.json）
        self.runtime_lock_path: Optional[Path] = None
        self.bb_sites_dir = Path.home() / ".bb-browser" / "bb-sites"
        if self.control_root is not None:
            self.runtime_lock_path = self.control_root.parent / "phase2_runtime_lock.json"

    # -- 工具 ---------------------------------------------------------------
    def _incoming_dir(self) -> Path:
        if self.exchange_root is None:
            raise RuntimeError("exchange_root 未配置，无法读取 incoming")
        d = self.exchange_root / "incoming"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _processed_dir(self) -> Path:
        if self.exchange_root is None:
            raise RuntimeError("exchange_root 未配置，无法归档")
        d = self.exchange_root / "processed"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _scan_manifest_files(self, manifest_id: str) -> List[PendingFile]:
        """扫描 incoming，返回命中本次 manifest_id 的全部结果文件（list[PendingFile]）。

        按头部 task_manifest_id + task_id + source_key 精确匹配，
        同一个平台多个关键词 → 多个 task_id 文件，互不覆盖。
        """
        found: List[PendingFile] = []
        incoming = self._incoming_dir()
        for f in incoming.glob("*.txt"):
            try:
                text = f.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            header = parse_header(text)
            if header.get(HEADER_TASK_MANIFEST_ID) != manifest_id:
                continue
            task_id = header.get(HEADER_TASK_ID)
            source_key = header.get(HEADER_SOURCE_KEY)
            if not task_id or not source_key:
                continue
            try:
                st = f.stat()
                size = st.st_size
                collected_at = st.st_mtime
            except OSError:
                size, collected_at = 0, None
            found.append(PendingFile(
                manifest_id=manifest_id,
                task_id=task_id,
                source_key=source_key,
                path=f,
                file_size=size,
                collected_at=collected_at,
            ))
        return found

    def _wait_for_results(
        self, manifest_id: str, expected: List[Tuple[str, str]]
    ) -> List[PendingFile]:
        """轮询 incoming，直到所有期望 (task_id, source_key) 出现且大小连续两次一致。

        expected 来自 manifest 实际生成的规则（含多关键词多文件）。
        超时或任一任务始终缺失 → 抛 RuntimeError（all-or-nothing）。
        """
        expected_set = set(expected)
        deadline = time.time() + self.timeout_seconds
        last_seen: dict = {}
        stable: set = set()
        while time.time() < deadline:
            files = self._scan_manifest_files(manifest_id)
            present: dict = {}
            for pf in files:
                present[(pf.task_id, pf.source_key)] = pf.file_size
            for key in expected_set:
                if key in present:
                    if last_seen.get(key) == present[key]:
                        stable.add(key)
                    else:
                        stable.discard(key)
                else:
                    stable.discard(key)
            last_seen = present
            if expected_set.issubset(stable):
                by_key = {(pf.task_id, pf.source_key): pf for pf in files}
                return [by_key[k] for k in expected]
            # 心跳：延长锁的 last_seen，避免等待期间被误判 stale
            if self._mutex is not None:
                self._mutex.heartbeat()
            time.sleep(self.poll_interval_seconds)
        raise CollectorError(
            ERR_TIMEOUT,
            f"等待 bb-browser worker 产出结果超时（manifest_id={manifest_id}）；"
            f"已就绪任务={sorted(stable)}，期望={sorted(expected_set)}。"
            f"可能原因：某平台 adapter 返回 401/403/login/auth，或 CDP/daemon 不可达。",
        )

    # -- fetch --------------------------------------------------------------
    def _outgoing_other_tasks(self, manifest_id: str) -> List[Path]:
        """返回 outgoing 中与本次 manifest_id 不同的其它未处理 .txt。

        Plan A 并发控制：只要存在任何「其它」任务文件，fetch() 就拒绝写入新
        manifest，交由下一轮重试。自身刚写入的 manifest（同 stem）不算「其它」。
        """
        if self.control_root is None:
            return []
        outgoing = self.control_root / "outgoing"
        if not outgoing.exists():
            return []
        return [f for f in outgoing.glob("*.txt") if f.stem != manifest_id]

    def preflight(self, *, test_mode: Optional[bool] = None) -> Tuple[bool, list]:
        """§八：运行前校验 runtime lock。

        - runtime_lock_path 未配置（如 control_root 未设置）→ 跳过（True）。
        - 锁文件存在 → 校验并返回 (ok, diffs)。
        - 锁文件缺失：
            * 生产环境（test_mode=False，默认）→ 返回 (False, [lock_file missing])，
              即 runtime_drift，fetch() 将阻断并生成差异报告（绝不 fail-open）。
            * 测试环境（test_mode=True 或环境变量 BBBROWSER_TEST_MODE=1）→ 跳过（True），
              供单元测试使用，不得用生产逻辑 fail-open。
        """
        effective_test_mode = self._test_mode if test_mode is None else test_mode
        if self.runtime_lock_path is None:
            return True, []
        if not self.runtime_lock_path.exists():
            if effective_test_mode:
                return True, []
            return False, [{"field": "lock_file", "expected": "exists", "actual": "missing"}]
        return verify_runtime_lock(self.runtime_lock_path, bb_sites_dir=self.bb_sites_dir)

    def recover_prior_runs(self, *, reason: str = "pre_create_recovery") -> List[tuple]:
        """§四/§五：新任务创建前检查 outgoing/stale，优先重试未完成任务。

        - 仅作用于尚未创建当前 manifest 之前的既有 manifest；
        - S_RETRYABLE → retry_incomplete（只重试未完成的 task_id/source_key）；
        - S_REJECTED → 已达上限，保持 rejected（已写 reason.json，不重复处理）；
        - 活跃锁（active/processing）→ 不在此处理，交由后续 mutex.acquire 判定
          （活跃进程仍在工作，新任务应被 worker_busy 拒绝，而非抢占）。
        返回 [(manifest_id, action), ...] 供审计。
        """
        if self.control_root is None or self.exchange_root is None:
            return []
        # 局部导入：避免与 recovery 模块互相 import（recovery 也从 collector 取 parse_manifest_rules）
        from app.collectors.bb_browser_recovery import (
            ManifestRecovery,
            S_ACK_CONFIRMED,
            S_REJECTED,
            S_RETRYABLE,
        )
        rec = ManifestRecovery(self.control_root, self.exchange_root, max_retries=3)
        acted: List[tuple] = []
        outgoing = self.control_root / "outgoing"
        stale_dir = self.control_root / "stale"
        # 扫描范围：outgoing（活跃/残留）+ stale（已被回收迁移的孤儿 manifest）。
        # recovery/ 下的 retry sidecar 由 rec.inspect() 读取，参与重试次数判定。
        candidates: List[str] = []
        for d in (outgoing, stale_dir):
            if not d.exists():
                continue
            for f in sorted(d.glob("*.txt")):
                if f.stem not in candidates:
                    candidates.append(f.stem)
        if not candidates:
            return acted
        for mid in candidates:
            # 绝不处理当前新任务自己的 manifest（避免新任务误消费/自我重试）
            if mid == self._current_manifest_id:
                continue
            st = rec.inspect(mid)
            if st.state == S_RETRYABLE:
                rec.retry_incomplete(mid, reason=reason)
                acted.append((mid, "retry_incomplete"))
            elif st.state == S_REJECTED:
                # 已达重试上限：移入 rejected/ 并写 reason（幂等，绝不删除 incoming）
                rec.reject(mid, reason or "retry_exhausted")
                acted.append((mid, "rejected"))
            elif st.state == S_ACK_CONFIRMED:
                # 已 ack 完成的任务不得再次 retry，直接归档
                rec.archive(mid)
                acted.append((mid, "archived_ack_confirmed"))
            # active/processing 交给 mutex.acquire
        return acted

    def _write_drift_report(self, diffs: list) -> None:
        if self.control_root is None:
            return
        report = {
            "detected_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "code": ERR_RUNTIME_DRIFT,
            "diffs": diffs,
        }
        p = self.control_root / "runtime_drift.json"
        # Phase 3A 修复：control_root 可能尚未创建（例如缺锁在 mkdir 之前就已阻断），
        # 原实现直接 write_text → OSError 被吞掉，导致日志声称已生成报告但文件不存在。
        try:
            self.control_root.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            logger.error("runtime drift 阻断：已生成差异报告 %s，diffs=%s", p, diffs)
        except OSError as exc:
            logger.error(
                "runtime drift 阻断：差异报告写入失败 %s（%s），diffs=%s", p, exc, diffs
            )

    def fetch(
        self,
        keywords: Optional[list[str]] = None,
        region_kw: Optional[list[str]] = None,
        topic_kw: Optional[list[str]] = None,
        **kwargs,
    ) -> list[dict]:
        """生成 manifest → 交给运行中 worker → 读取并归一化本次结果。

        不直连 Node CLI、不直写 DB。仅返回标准化 Opinion dict 列表。
        任一平台失败（超时/401/缺结果）→ 抛异常，不返回空列表、不伪装成功。
        """
        if self.control_root is None or self.exchange_root is None:
            raise RuntimeError("control_root / exchange_root 未配置，BBBrowserCollector 无法运行")
        if not self.platforms:
            raise RuntimeError("无可用平台（白名单为空或被全部排除）")

        # §八：运行前 runtime lock preflight；漂移则阻断（不创建新 manifest）
        ok, diffs = self.preflight()
        if not ok:
            self._write_drift_report(diffs)
            raise CollectorError(
                ERR_RUNTIME_DRIFT,
                f"运行时漂移，已阻断并生成差异报告：{diffs}",
            )

        search_plats = [p for p in self.platforms if PLATFORM_META[p]["kind"] == "search"]
        hot_plats = [p for p in self.platforms if PLATFORM_META[p]["kind"] == "hot"]
        keywords = [str(k).strip() for k in (keywords or []) if str(k).strip()]
        if search_plats and not keywords:
            raise RuntimeError(
                f"搜索型平台 {search_plats} 需要至少一个关键词，但本次关键词为空；"
                f"无法生成 search rule（manifest 要求 match_terms 非空）。"
            )

        manifest_id = uuid.uuid4().hex
        self._current_manifest_id = manifest_id

        # ---- 新任务创建前：优先恢复 stale/partial 既有 manifest（§四/§五）----
        # 只重试未完成的 (task_id, source_key)，不误消费旧 manifest（按 manifest_id 精确匹配）。
        try:
            recovery_actions = self.recover_prior_runs(reason="pre_create_recovery")
            if recovery_actions:
                logger.info("recover_prior_runs: %s", recovery_actions)
        except Exception:
            logger.exception("recover_prior_runs 异常（不影响本次新任务创建）")

        # ---- outgoing 跨进程原子互斥（§三，替代旧 Plan A TOCTOU）----
        # 原子 O_EXCL 创建锁文件；已有活跃锁 → 抛 worker_busy（§五）；
        # 已有 stale 锁 → 回收孤儿 manifest 到 stale/ 后继续。绝不删除他人 manifest。
        outgoing = self.control_root / "outgoing"
        mutex = OutgoingMutex(outgoing, stale_dir=self.control_root / "stale")
        self._mutex = mutex
        mutex.acquire(manifest_id)  # 持有失败（活跃锁）会抛 OutgoingLockError(worker_busy)

        try:
            # 1) 原子写入 manifest
            text = build_manifest(
                manifest_id,
                keywords,
                self.platforms,
                keyword_config_version="1",
                policy_version="1",
            )
            write_manifest_atomic(outgoing, manifest_id, text)
            logger.info("BBBrowserCollector 已写入 manifest=%s 到 outgoing（关键词=%s）",
                        manifest_id, keywords)

            # 2) 等待本次结果（按 manifest 实际规则计算期望任务集合）
            expected = expected_tasks_for_manifest(text)
            files = self._wait_for_results(manifest_id, expected)

            # 3) 解析 + 逐条归一化（同一平台多文件全部计入，不丢失）
            items: list[dict] = []
            raw_total = 0
            normalized_total = 0
            per_platform: dict[str, int] = {}
            for pf in files:
                rec = parse_record_text(pf.path.read_text(encoding="utf-8", errors="ignore"))
                if rec["error"] is not None:
                    code = classify_adapter_error(rec["error"], pf.source_key)
                    raise CollectorError(
                        code,
                        f"平台 {pf.source_key} adapter 返回错误（manifest_id={manifest_id} "
                        f"task_id={pf.task_id}）：{rec['error']}",
                    )
                if rec["content"] is None:
                    raise CollectorError(
                        ERR_ADAPTER_ERROR,
                        f"平台 {pf.source_key} 结果无法解析（manifest_id={manifest_id}，"
                        f"文件={pf.path.name}）",
                    )
                raw_total += raw_item_count(pf.source_key, rec["content"])
                norm = normalize_record(pf.source_key, rec["content"], self.max_items_per_platform)
                normalized_total += len(norm)
                per_platform[pf.source_key] = per_platform.get(pf.source_key, 0) + len(norm)
                items.extend(norm)

            if not items:
                raise CollectorError(
                    ERR_EMPTY_RESULT,
                    f"bb-browser 本次采集返回 0 条有效条目（manifest_id={manifest_id}），"
                    f"各平台条数={per_platform}。不伪装成功。",
                )

            # 口径：last_fetched_raw=上游原始（截断前）；returned=len(items)（截断后）
            self.last_fetched_raw = raw_total
            self.normalized_count = normalized_total
            self.last_not_exported_returned = len(items)
            self._pending_files = [pf.path for pf in files]
            logger.info(
                "BBBrowserCollector 归一化完成 manifest=%s 平台=%s 原始=%d 归一化=%d 返回=%d",
                manifest_id, per_platform, raw_total, normalized_total, len(items),
            )
            return items
        finally:
            # 释放互斥锁（manifest 文件在 ack 成功后由 ack_pending_export 清理）
            mutex.release()

    # -- ack -----------------------------------------------------------------
    @staticmethod
    def _files_equal(a: Path, b: Path) -> bool:
        try:
            if a.stat().st_size != b.stat().st_size:
                return False
        except OSError:
            return False

        def _sha(p: Path) -> str:
            h = hashlib.sha256()
            with open(p, "rb") as fh:
                for chunk in iter(lambda: fh.read(65536), b""):
                    h.update(chunk)
            return h.hexdigest()

        try:
            return _sha(a) == _sha(b)
        except OSError:
            return False

    def _ack_pending_dir(self) -> Path:
        if self.exchange_root is None:
            raise RuntimeError("exchange_root 未配置，无法持久化 ack-pending 记录")
        d = self.exchange_root / "ack_pending"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _write_ack_record(self, pending: list, processed: Path, run_id) -> None:
        """仅在 CollectorService 完成入库与分析后调用，写入 ack-pending 持久记录。"""
        mid = self._current_manifest_id
        if not mid:
            return
        rec = {
            "manifest_id": mid,
            "collector_run_id": run_id,
            "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "files": [
                {"source": str(p), "target": str(processed / p.name)}
                for p in pending
            ],
        }
        (self._ack_pending_dir() / f"{mid}.json").write_text(
            json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    @staticmethod
    def _ack_files(files: list, processed: Path) -> Tuple[bool, str]:
        """幂等移动（§六）：files 为 list[Path 或 dict(source,target)]。

        返回 (成功?, 详情)。四态：
          source 存在 + target 不存在 → 移动；
          source 缺失 + target 一致 → confirmed；
          source/target 内容不一致 → 拒绝覆盖（失败）；
          两者都不存在 → recovery_failed（失败）。
        移动中途失败 → 回滚已移动文件。
        """
        plan: list = []
        for f in files:
            if isinstance(f, dict):
                src = Path(f["source"])
                dst = Path(f["target"])
            else:
                src = Path(f)
                dst = processed / src.name
            if src.exists():
                if dst.exists():
                    if BBBrowserCollector._files_equal(src, dst):
                        plan.append((src, dst, "confirmed"))
                    else:
                        return False, f"target differs (reject overwrite): {src.name}"
                else:
                    plan.append((src, dst, "move"))
            else:
                if dst.exists():
                    plan.append((src, dst, "confirmed"))
                else:
                    return False, f"source missing (recovery_failed): {src.name}"

        moved: list = []
        for src, dst, action in plan:
            if action != "move":
                continue
            try:
                os.replace(src, dst)
                moved.append(src)
            except OSError as exc:
                logger.error("ack：移动失败 %s -> %s：%s；回滚已移动文件", src, dst, exc)
                for m in moved:
                    try:
                        os.replace(processed / m.name, m)
                    except OSError as rb:
                        logger.error("ack：回滚失败 %s：%s", m, rb)
                return False, f"move failed: {exc}"
        return True, ""

    def ack_pending_export(self, collector_run_id=None) -> bool:
        """把本次 fetch 产生的 incoming 文件移动到 processed（幂等 + 跨进程可恢复）。

        - 若提供 collector_run_id（CollectorService 入库成功后），先持久化
          ack-pending 记录，进程崩溃后由 recover_pending_ack() 继续。
        - 幂等四态见 _ack_files；失败时不清理 _pending_files（可重试）。
        仅由 CollectorService 在「入库 + 分析成功」后调用。
        """
        pending = list(self._pending_files)
        if not pending:
            return True
        processed = self._processed_dir()
        if collector_run_id is not None:
            self._write_ack_record(pending, processed, collector_run_id)

        ok, detail = self._ack_files(pending, processed)
        if not ok:
            logger.error("ack 失败：%s", detail)
            return False

        self._pending_files = []
        # 成功：清理 ack-pending 记录 + outgoing manifest
        if collector_run_id is not None and self._current_manifest_id:
            try:
                (self._ack_pending_dir() / f"{self._current_manifest_id}.json").unlink()
            except OSError:
                pass
        if self._current_manifest_id and self.control_root is not None:
            mpath = self.control_root / "outgoing" / f"{self._current_manifest_id}.txt"
            try:
                mpath.unlink()
            except OSError:
                pass
        return True

    @classmethod
    def recover_pending_ack(cls, exchange_root: str | Path) -> dict:
        """跨进程恢复：新 Collector 实例读取 exchange_root/ack_pending/*.json，
        幂等完成遗留 ack（不依赖旧实例的 _pending_files）。

        只处理「有 ack-pending 记录」的文件（即有成功 CollectorRun 的），
        绝不自动 ack 孤立 incoming；旧 incoming 保持不变。
        """
        exchange_root = Path(exchange_root)
        ack_dir = exchange_root / "ack_pending"
        processed = exchange_root / "processed"
        processed.mkdir(parents=True, exist_ok=True)
        result: dict = {"records": [], "recovered": 0, "failed": 0}
        if not ack_dir.exists():
            return result
        for rf in sorted(ack_dir.glob("*.json")):
            try:
                rec = json.loads(rf.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                result["failed"] += 1
                result["records"].append({"manifest_id": rf.stem, "ok": False, "detail": "bad_record"})
                continue
            ok, detail = cls._ack_files(rec.get("files", []), processed)
            if ok:
                try:
                    rf.unlink()
                except OSError:
                    pass
                result["recovered"] += 1
            else:
                result["failed"] += 1
            result["records"].append({
                "manifest_id": rec.get("manifest_id", rf.stem),
                "collector_run_id": rec.get("collector_run_id"),
                "ok": ok,
                "detail": detail,
            })
        return result
