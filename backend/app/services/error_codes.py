"""Stable, read-only error semantics for collector health reporting.

The original CollectorRun.error_msg remains the source of truth.  This module
only maps that text (and optional HTTP status) to a small, stable vocabulary.
"""
from __future__ import annotations

from enum import Enum
import re


class ErrorCode(str, Enum):
    TOKEN_EXPIRED = "TOKEN_EXPIRED"
    AUTH_FAILED = "AUTH_FAILED"
    HTTP_ERROR = "HTTP_ERROR"
    TIMEOUT = "TIMEOUT"
    PARSE_ERROR = "PARSE_ERROR"
    NO_DATA = "NO_DATA"
    UNKNOWN_ERROR = "UNKNOWN_ERROR"


_TOKEN_RE = re.compile(
    r"token\s*(?:invalid|expired)|access[_ ]token\s*expired|token.*(?:过期|无效)|令牌.*(?:过期|无效)",
    re.IGNORECASE,
)
_AUTH_RE = re.compile(
    r"unauthorized|authentication|auth(?:entication)?[_ -]?failed|认证失败|未授权",
    re.IGNORECASE,
)


def normalize_error_code(error_message: str | None, *, http_status: int | None = None) -> str:
    """Map provider-specific text to :class:`ErrorCode` without altering it."""
    message = str(error_message or "")
    lowered = message.lower()
    if http_status == 401 or re.search(r"\b401\b", lowered) or _TOKEN_RE.search(message):
        return ErrorCode.TOKEN_EXPIRED.value
    if http_status == 403 or _AUTH_RE.search(message):
        return ErrorCode.AUTH_FAILED.value
    if re.search(r"\b(?:408|429|5\d\d)\b|http\s*error|status\s*code", lowered):
        return ErrorCode.HTTP_ERROR.value
    if "timeout" in lowered or "timed out" in lowered or "超时" in message:
        return ErrorCode.TIMEOUT.value
    if "json" in lowered or "parse" in lowered or "解析" in message or "response structure" in lowered:
        return ErrorCode.PARSE_ERROR.value
    if "no data" in lowered or "empty" in lowered or "无数据" in message or "空数据" in message:
        return ErrorCode.NO_DATA.value
    return ErrorCode.UNKNOWN_ERROR.value


# Short alias for callers/tests that prefer an error-code naming verb.
classify_error_code = normalize_error_code
