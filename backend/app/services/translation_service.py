"""百度翻译服务（独立翻译 API）。

与 LLM/搜索服务解耦，专用于舆情详情弹窗「翻译」按钮。
- 官方标准版 API：`https://fanyi-api.baidu.com/api/trans/vip/translate`（GET）
- 签名：sign = md5(appid + q + salt + secret)
- 免费额度 200 万字符/月，国内直连，无需代理。
- 仅支持纯文本：调用前剥离 HTML 标签；超长文本按句分块翻译后拼接。
"""
from __future__ import annotations

import hashlib
import re
import time

import requests

from app.core.config import settings

_HTML_TAG_RE = re.compile(r"<[^>]+>")
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[。！？!?.\n])")
_CACHE: dict[tuple[str, str, str], tuple[float, str]] = {}
_CACHE_TTL = 3600  # 秒
_MAX_CHUNK = 5000  # 百度单次 q 上限约 6000，留余量


class TranslationError(Exception):
    """翻译调用失败（网络/签名/配额/未配置等）。"""


def _strip_html(text: str) -> str:
    return _HTML_TAG_RE.sub(" ", text or "").strip()


def _chunk(text: str, max_len: int = _MAX_CHUNK) -> list[str]:
    if len(text) <= max_len:
        return [text]
    parts = _SENTENCE_SPLIT_RE.split(text)
    chunks: list[str] = []
    cur = ""
    for p in parts:
        if cur and len(cur) + len(p) > max_len:
            chunks.append(cur)
            cur = p
        else:
            cur += p
    if cur:
        chunks.append(cur)
    return [c for c in chunks if c.strip()] or [text]


def translate_text(
    text: str,
    target_lang: str = "zh",
    source_lang: str = "auto",
) -> str:
    """翻译文本，返回译文。缺凭证时抛 TranslationError。"""
    text = _strip_html(text).strip()
    if not text:
        return ""

    # 去掉手动编辑 .env 时可能带入的首尾空白/引号，避免签名因 secret 含不可见字符而 54001。
    app_id = (settings.baidu_translate_app_id or "").strip()
    secret = (settings.baidu_translate_secret or "").strip()
    if not app_id or not secret:
        raise TranslationError(
            "翻译服务未配置（缺少 BAIDU_TRANSLATE_APP_ID / BAIDU_TRANSLATE_SECRET）"
        )

    cache_key = (text, target_lang, source_lang)
    now = time.time()
    cached = _CACHE.get(cache_key)
    if cached is not None and now - cached[0] < _CACHE_TTL:
        return cached[1]

    endpoint = settings.baidu_translate_endpoint
    salt = str(int(now * 1000))
    pieces = _chunk(text)
    translated: list[str] = []

    for piece in pieces:
        sign = hashlib.md5(
            (app_id + piece + salt + secret).encode("utf-8")
        ).hexdigest()
        params = {
            "q": piece,
            "from": source_lang,
            "to": target_lang,
            "appid": app_id,
            "salt": salt,
            "sign": sign,
        }
        try:
            resp = requests.get(endpoint, params=params, timeout=10)
            data = resp.json()
        except Exception as exc:  # noqa: BLE001
            raise TranslationError(f"翻译请求失败：{exc}") from exc

        if data.get("error_code"):
            masked = (app_id[:4] + "****" + app_id[-2:]) if len(app_id) > 6 else app_id
            raise TranslationError(
                f"翻译失败[{data.get('error_code')}]：{data.get('error_msg')}（appid={masked}）"
            )
        for item in data.get("trans_result", []):
            translated.append(item.get("dst", ""))

    result = "\n".join(translated)
    _CACHE[cache_key] = (now, result)
    return result
