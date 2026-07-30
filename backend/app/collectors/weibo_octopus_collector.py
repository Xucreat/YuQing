"""微博数据源采集器（Phase Weibo-1：经八爪鱼开放 API 获取，非直爬）。

定位：
  - 微博短文（weibo_post）优先；评论（weibo_comment）留作后续扩展
    （可另插一行 data_sources，config_json 覆盖 task_id 与 source_type）。
  - 复用现有链路：八爪鱼API -> WeiboOctopusCollector.fetch() ->
    CollectorService（去重/入库/规则分析/RiskEngine）-> Opinion -> 事件聚合/预警。
    不新建微博专用表、不引入 Redis/Celery。

设计约束（与 GrokCollector 同范式）：
  - 继承 BaseCollector；fetch() 兼容 CollectorService 的统一参数契约。
  - Collector 禁止直接操作数据库。
  - 凭据全部来自 settings（BAZHU_* 环境变量），绝不写入 data_sources.config_json
    或硬编码；凭据/任务 ID 缺失 = 硬失败（RuntimeError），由 CollectorService
    记入 CollectorRun(status=failed)，在采集日志中可见，而非静默 0 条。
  - settings.weibo_enabled=False 时 fetch 直接返回 []（运行总开关，双保险；
    数据源级启停仍以 data_sources.enabled 为准）。

八爪鱼开放 API（https://openapi.bazhuayu.com）：
  - POST /token                      username/password/grant_type=password -> access_token
  - GET  /data/notexported?taskId&size   拉取未导出数据（增量语义）
  - POST /data/markexported              确认已导出（body: {taskId}）
  路径可经 config_json 覆盖（api 变更时免改代码）。

数据映射（用户约定）：
  title=微博标题或首句 / content=正文 / source="weibo" / source_type="weibo_post"
  url=微博链接 / publish_time=发布时间 / author=发布用户
  engagement={"likes","comments","reposts"} / external_id=微博 mid
"""
from __future__ import annotations

import logging
import re
import time
from typing import Any, Dict, List, Optional

from app.collectors.base import BaseCollector
from app.collectors.common import _parse_date_string, make_session, matches_keywords
from app.core.config import settings

logger = logging.getLogger(__name__)

# 八爪鱼任务导出字段名由任务模板自定义，此处内置常见候选名（可被 config_json
# 的 field_map 覆盖）。匹配大小写不敏感。
DEFAULT_FIELD_MAP: Dict[str, List[str]] = {
    "title": ["title", "标题", "微博标题"],
    "content": [
        "content", "正文", "微博正文", "微博内容", "博文内容", "内容", "text", "博文",
    ],
    "url": ["url", "链接", "微博链接", "详情链接", "link", "href", "页面网址"],
    "publish_time": ["publish_time", "发布时间", "时间", "date", "time", "created_at"],
    "author": ["author", "作者", "用户名", "昵称", "nickname", "用户", "博主", "博主昵称"],
    "likes": ["likes", "点赞", "点赞数", "attitudes_count", "like_count"],
    "comments": ["comments", "评论", "评论数", "comments_count", "comment_count"],
    "reposts": ["reposts", "转发", "转发数", "reposts_count", "repost_count"],
    "external_id": ["external_id", "mid", "weibo_id", "微博id", "id"],
    "comment_author": ["comment_author", "评论人", "评论用户", "评论者"],
    "comment_content": ["comment_content", "评论内容", "评论正文", "comment_text"],
    "comment_time": ["comment_time", "评论时间", "评论发布时间"],
    "comment_author_url": ["comment_author_url", "评论人主页链接", "评论人主页"],
}

_SENTENCE_SPLIT = re.compile(r"[。！？!?\n]")
_WEIBO_DETAIL_URL = re.compile(r"^https?://(?:www\.)?weibo\.com/\d+/[A-Za-z0-9]+")


def _first_sentence(text: str, limit: int = 100) -> str:
    """取首句作为标题（无标题字段时的降级），超长截断。"""
    for seg in _SENTENCE_SPLIT.split(text):
        seg = seg.strip()
        if seg:
            return seg[:limit]
    return text.strip()[:limit]


def _to_int(v: Any) -> Optional[int]:
    """互动数安全转 int：'1.2万' / '3,456' / None 均可容错。"""
    if v is None:
        return None
    try:
        s = str(v).strip().replace(",", "")
        if not s:
            return None
        if s.endswith("万"):
            return int(float(s[:-1]) * 10000)
        if s.endswith("亿"):
            return int(float(s[:-1]) * 100000000)
        return int(float(s))
    except Exception:  # noqa: BLE001
        return None


class WeiboOctopusCollector(BaseCollector):
    """八爪鱼 API 微博采集器（微博短文）。"""

    source_name = "微博"
    data_source_key = "weibo_octopus"

    # 类级 token 缓存（同进程内多次采集复用；expires_in 提前 60s 失效）
    _token_cache: dict = {"token": None, "expire_at": 0.0}

    def __init__(self, **cfg: Any) -> None:
        # config_json 仅允许非敏感项：task_id/base_url/路径/field_map/开关等。
        # 凭据（api_key/username/password）一律来自 settings，传入即忽略。
        self.base_url: str = (cfg.get("base_url") or settings.bazhu_base_url or "").rstrip("/")
        self.task_id: str = str(cfg.get("task_id") or settings.bazhu_task_id or "")
        self.fetch_size: int = int(cfg.get("fetch_size") or settings.bazhu_fetch_size)
        self.mark_exported: bool = bool(cfg.get("mark_exported", settings.bazhu_mark_exported))
        self.filter_by_keywords: bool = bool(cfg.get("filter_by_keywords", True))
        self.source_type: str = str(cfg.get("source_type") or "weibo_post")
        self.timeout: int = int(cfg.get("timeout", 30))
        # API 路径可覆盖（八爪鱼版本变更免改代码）
        self.path_token: str = cfg.get("path_token", "/token")
        self.path_notexported: str = cfg.get("path_notexported", "/data/notexported")
        self.path_mark_exported: str = cfg.get("path_mark_exported", "/data/markexported")
        # 字段映射：默认候选 + config 覆盖（覆盖为整键替换）
        fm = dict(DEFAULT_FIELD_MAP)
        for k, v in (cfg.get("field_map") or {}).items():
            fm[k] = v if isinstance(v, list) else [str(v)]
        self.field_map = fm
        self.session = make_session()
        self.last_fetched_raw: int = 0
        self.last_comments_seen: int = 0
        self.last_comments_skipped: int = 0
        self.last_not_exported_total: Optional[int] = None
        self.last_not_exported_returned: int = 0
        self._pending_export_token: Optional[str] = None

    # ------------------------------------------------------------------
    # 凭证（缺失即硬失败，让 CollectorRun 记 failed 而非静默 0 条）
    # ------------------------------------------------------------------
    def _get_token(self) -> str:
        if settings.bazhu_api_key:
            return settings.bazhu_api_key
        if not (settings.bazhu_username and settings.bazhu_password):
            raise RuntimeError(
                "八爪鱼凭据未配置：请在生产 .env 设置 BAZHU_API_KEY（直接作为 access_token）"
                "或 BAZHU_USERNAME/BAZHU_PASSWORD（自动换取 token）；"
                "禁止写入 data_sources.config_json 或硬编码。"
            )
        cache = WeiboOctopusCollector._token_cache
        if cache["token"] and time.time() < cache["expire_at"]:
            return cache["token"]
        resp = self.session.post(
            f"{self.base_url}{self.path_token}",
            json={
                "username": settings.bazhu_username,
                "password": settings.bazhu_password,
                "grant_type": "password",
            },
            timeout=self.timeout,
        )
        if resp.status_code != 200:
            raise RuntimeError(f"八爪鱼获取 token 失败：HTTP {resp.status_code} {resp.text[:200]}")
        data = (resp.json() or {}).get("data") or {}
        token = data.get("access_token")
        if not token:
            raise RuntimeError(f"八爪鱼 token 响应缺少 access_token：{str(resp.text)[:200]}")
        expires_in = float(data.get("expires_in") or 3600)
        cache["token"] = token
        cache["expire_at"] = time.time() + max(60.0, expires_in - 60.0)
        return token

    # ------------------------------------------------------------------
    # 主入口
    # ------------------------------------------------------------------
    def fetch(
        self,
        keywords: Optional[List[str]] = None,
        region_kw: Optional[List[str]] = None,
        topic_kw: Optional[List[str]] = None,
    ) -> List[dict]:
        self.last_fetched_raw = 0
        self.last_comments_seen = 0
        self.last_comments_skipped = 0
        self.last_not_exported_total = None
        self.last_not_exported_returned = 0
        self._pending_export_token = None
        # region_kw/topic_kw 为统一 CollectorService 契约参数；微博仍沿用
        # keywords 的全局关键词过滤逻辑，暂不单独消费地域/主题分组。
        del region_kw, topic_kw
        # 运行总开关（双保险）：关闭时静默跳过，不影响其他采集器。
        if not settings.weibo_enabled:
            logger.info("WeiboOctopusCollector: WEIBO_ENABLED=False，跳过微博采集")
            return []
        if not self.task_id:
            raise RuntimeError(
                "BAZHU_TASK_ID 未配置：无法定位八爪鱼微博采集任务"
                "（生产 .env 设置 BAZHU_TASK_ID，或 data_sources.config_json 提供 task_id）。"
            )

        token = self._get_token()
        rows = self._fetch_not_exported(token)
        items: List[dict] = []
        items_by_key: Dict[str, dict] = {}
        parsed_rows = 0
        mapped_rows = 0
        dropped_missing_content = 0
        dropped_other = 0
        filtered_by_keywords = 0
        duplicate_post_rows = 0
        comments_seen = 0
        comments_skipped = 0
        for row in rows:
            has_comment = self._row_has_comment(row)
            if has_comment:
                comments_seen += 1
            item, drop_reason = self._map_row_with_reason(row)
            if item is None:
                if has_comment:
                    parsed_rows += 1
                    comments_skipped += 1
                if drop_reason == "missing_content":
                    dropped_missing_content += 1
                else:
                    dropped_other += 1
                continue
            parsed_rows += 1
            mapped_rows += 1
            if has_comment:
                comments_skipped += 1
                item["comment_seen"] = True
                item["comment_count_seen"] = 1
            else:
                item["comment_seen"] = False
                item["comment_count_seen"] = 0
            # 与全站一致的区域相关性关键词过滤（keywords 表驱动；空关键词放行）。
            if self.filter_by_keywords and keywords is not None:
                if not matches_keywords(f"{item['title']} {item['content']}", keywords):
                    filtered_by_keywords += 1
                    continue
            dedup_key = self._post_dedup_key(item)
            if dedup_key and dedup_key in items_by_key:
                duplicate_post_rows += 1
                existing = items_by_key[dedup_key]
                existing["comment_count_seen"] = int(existing.get("comment_count_seen") or 0) + int(
                    item.get("comment_count_seen") or 0
                )
                existing["comment_seen"] = bool(existing.get("comment_seen")) or bool(item.get("comment_seen"))
                continue
            items.append(item)
            if dedup_key:
                items_by_key[dedup_key] = item

        # 仅保存确认所需的 token；确认必须由 CollectorService 在入库成功后触发。
        if rows and self.mark_exported:
            self._pending_export_token = token

        self.last_fetched_raw = parsed_rows
        self.last_comments_seen = comments_seen
        self.last_comments_skipped = comments_skipped
        logger.info(
            (
                "WeiboOctopusCollector: raw_rows=%d mapped_rows=%d "
                "parsed_rows=%d dropped_missing_content=%d dropped_other=%d "
                "filtered_by_keywords=%d duplicate_post_rows=%d "
                "comments_seen=%d comments_skipped=%d retained=%d"
            ),
            len(rows),
            mapped_rows,
            parsed_rows,
            dropped_missing_content,
            dropped_other,
            filtered_by_keywords,
            duplicate_post_rows,
            comments_seen,
            comments_skipped,
            len(items),
        )
        return items

    # ------------------------------------------------------------------
    # 八爪鱼数据接口
    # ------------------------------------------------------------------
    def _fetch_not_exported(self, token: str) -> List[dict]:
        resp = self.session.get(
            f"{self.base_url}{self.path_notexported}",
            params={"taskId": self.task_id, "size": self.fetch_size},
            headers={"Authorization": f"Bearer {token}"},
            timeout=self.timeout,
        )
        if resp.status_code != 200:
            raise RuntimeError(
                f"八爪鱼拉取数据失败：HTTP {resp.status_code} {resp.text[:200]}"
            )
        payload = resp.json() or {}
        data = payload.get("data") or {}
        rows = data.get("data") or data.get("dataList") or []
        if not isinstance(rows, list):
            raise RuntimeError(f"八爪鱼数据响应结构异常：{str(payload)[:200]}")
        total = data.get("total")
        try:
            self.last_not_exported_total = int(total) if total is not None else None
        except (TypeError, ValueError):
            self.last_not_exported_total = None
        self.last_not_exported_returned = len(rows)
        return rows

    def can_ack_pending_export(self) -> bool:
        """Return whether a successful fetch has a pending export confirmation."""
        return self._pending_export_token is not None

    def ack_pending_export(self) -> bool:
        """Confirm the fetched export after CollectorService commits persistence."""
        token = self._pending_export_token
        if not token:
            return False
        self._confirm_exported(token)
        self._pending_export_token = None
        return True

    def _confirm_exported(self, token: str) -> None:
        resp = self.session.post(
            f"{self.base_url}{self.path_mark_exported}",
            json={"taskId": self.task_id},
            headers={"Authorization": f"Bearer {token}"},
            timeout=self.timeout,
        )
        if resp.status_code != 200:
            raise RuntimeError(
                f"确认导出失败：HTTP {resp.status_code} {resp.text[:200]}"
            )

    # ------------------------------------------------------------------
    # 行映射：八爪鱼自定义字段 -> 标准舆情 dict
    # ------------------------------------------------------------------
    def _pick(self, row: dict, field: str) -> Optional[Any]:
        """按候选名取值（大小写不敏感），返回第一个非空值。"""
        lowered = {str(k).strip().lower(): v for k, v in row.items()}
        for cand in self.field_map.get(field, []):
            v = lowered.get(cand.strip().lower())
            if v is not None and str(v).strip() != "":
                return v
        return None

    def _row_has_comment(self, row: Any) -> bool:
        if not isinstance(row, dict):
            return False
        return any(
            self._pick(row, field) is not None
            for field in ("comment_author", "comment_content", "comment_time", "comment_author_url")
        )

    def _post_dedup_key(self, item: dict) -> str:
        ext = (item.get("external_id") or "").strip()
        if ext:
            return f"external:{ext}"
        url = (item.get("url") or "").strip()
        if url and self._is_post_detail_url(url):
            return f"url:{url}"
        title = (item.get("title") or "").strip()
        pub = item.get("publish_time")
        if title and pub:
            return f"title_time:{title}|{pub}"
        return ""

    def _is_post_detail_url(self, url: str) -> bool:
        url = (url or "").strip()
        if not url:
            return False
        if url.startswith("https://t.cn/") or url.startswith("http://t.cn/"):
            return True
        return bool(_WEIBO_DETAIL_URL.match(url))

    def _map_row_with_reason(self, row: Any) -> tuple[Optional[dict], Optional[str]]:
        if not isinstance(row, dict):
            return None, "non_dict"
        content = str(self._pick(row, "content") or "").strip()
        if not content:
            # 无正文的行（模板抓取失败/空行）直接丢弃并记日志
            logger.debug("WeiboOctopusCollector: 丢弃无正文行 keys=%s", list(row.keys())[:8])
            return None, "missing_content"
        title = str(self._pick(row, "title") or "").strip() or _first_sentence(content)
        url = str(self._pick(row, "url") or "").strip()

        raw_time = self._pick(row, "publish_time")
        publish_time = _parse_date_string(str(raw_time)) if raw_time else None

        engagement = {}
        for key in ("likes", "comments", "reposts"):
            n = _to_int(self._pick(row, key))
            if n is not None:
                engagement[key] = n

        external_id = self._pick(row, "external_id")
        external_id = str(external_id).strip() if external_id else None
        if not external_id and self._is_post_detail_url(url):
            external_id = url

        return {
            "title": title[:500],
            "content": content,
            "source": "weibo",
            "source_type": self.source_type,
            "url": url,
            "publish_time": publish_time,
            "author": (str(self._pick(row, "author") or "").strip() or None),
            "engagement": engagement or None,
            "external_id": external_id,
        }, None

    def _map_row(self, row: dict) -> Optional[dict]:
        """将八爪鱼行映射为标准舆情 dict，保留原有公开调用行为。"""
        item, _ = self._map_row_with_reason(row)
        return item
