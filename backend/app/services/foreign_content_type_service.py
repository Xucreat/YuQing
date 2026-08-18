"""Deterministic, content-only classification for foreign opinions."""
from __future__ import annotations

import html
import re
from dataclasses import dataclass


CONTENT_TYPE_VERSION = "v1"
CONTENT_TYPES = frozenset(
    {
        "complaint",
        "consultation",
        "risk_event",
        "public_affairs",
        "news",
        "policy",
        "advertising",
        "entertainment",
        "irrelevant",
        "unknown",
    }
)

_TAG_RE = re.compile(r"<[^>]*>", flags=re.DOTALL)
_SPACE_RE = re.compile(r"\s+")


@dataclass(frozen=True)
class ContentTypeDecision:
    content_type: str
    version: str = CONTENT_TYPE_VERSION
    matched_signals: tuple[str, ...] = ()


# Order is intentional: a concrete risk event wins over broader policy/public
# affairs language when one article contains signals from several categories.
_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "risk_event",
        (
            r"事故|火灾|火警|爆炸|洪水|地震|台风|泥石流|山体滑坡|伤亡|死亡|冲突|袭击|枪击|爆发",
            r"\b(accident|fire|explosion|flood|earthquake|typhoon|landslide|casualt(?:y|ies)|killing|conflict|attack|shooting|outbreak)\b",
        ),
    ),
    (
        "complaint",
        (
            r"投诉|举报|申诉|维权|欠薪|侵权|不满|求曝光",
            r"\b(complaint|complain|grievance|petition|appeal|rights?\s*(?:violation|issue)|unpaid\s+wages|report\s+(?:a\s+)?(?:complaint|violation|issue|problem|abuse|fraud))\b",
        ),
    ),
    (
        "consultation",
        (
            r"咨询|求助|请问|询问|怎么办|求解",
            r"\b(question|consult(?:ation)?|advice|help|how\s+to|inquir(?:y|ies))\b",
        ),
    ),
    (
        "policy",
        (
            r"政策|法规|条例|规章|政府公告|通知|监管|部门发布|行政",
            r"\b(policy|regulation|law|ordinance|government\s+(?:notice|announcement)|regulator(?:y)?|administrative|ministry)\b",
        ),
    ),
    (
        "public_affairs",
        (
            r"公共服务|公共事务|基础设施|社区|民生|教育|医疗|交通|环境治理",
            r"\b(public\s+(?:service|affairs)|infrastructure|community|livelihood|education|healthcare|transport(?:ation)?|environmental)\b",
        ),
    ),
    (
        "advertising",
        (
            r"广告|促销|优惠|推广|赞助内容|带货",
            r"\b(advertisement|advertising|promotion|discount|sponsored|sponsorship|marketing)\b",
        ),
    ),
    (
        "entertainment",
        (
            r"娱乐|明星|电影|电视剧|综艺|游戏|演唱会|体育赛事",
            r"\b(entertainment|celebrity|movie|film|television|tv\s*show|gaming|concert|sports?)\b",
        ),
    ),
    (
        "irrelevant",
        (
            r"无关|不相关",
            r"\b(irrelevant|off[-\s]?topic|spam)\b",
        ),
    ),
)


def normalize_foreign_content(*values: str | None) -> str:
    """Strip markup/entities and normalize whitespace without using metadata."""
    parts: list[str] = []
    for value in values:
        if not value:
            continue
        cleaned = html.unescape(str(value))
        cleaned = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", cleaned)
        cleaned = _TAG_RE.sub(" ", cleaned)
        cleaned = _SPACE_RE.sub(" ", cleaned).strip()
        if cleaned:
            parts.append(cleaned)
    return " ".join(parts).casefold()


def _search(pattern: str, text: str) -> str | None:
    match = re.search(pattern, text, flags=re.IGNORECASE)
    return match.group(0) if match else None


def classify_foreign_content_type(
    *, title: str | None = None, summary: str | None = None, content: str | None = None
) -> ContentTypeDecision:
    text = normalize_foreign_content(title, summary, content)
    if len("".join(text.split())) < 8:
        return ContentTypeDecision("unknown")

    for category, patterns in _RULES:
        signals = tuple(signal for pattern in patterns if (signal := _search(pattern, text)))
        if signals:
            return ContentTypeDecision(
                category,
                version=CONTENT_TYPE_VERSION,
                matched_signals=signals[:5],
            )
    return ContentTypeDecision("news", version=CONTENT_TYPE_VERSION)
