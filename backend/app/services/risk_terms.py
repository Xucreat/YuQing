"""Shared rule semantics for real-world harm indicators."""
from __future__ import annotations

import re
from typing import Iterable


SCHOOL_HARM_KEYWORDS: frozenset[str] = frozenset(
    {"霸凌", "欺凌", "校园暴力", "殴打", "扇耳光", "被打", "体罚"}
)

# These weights are intentionally lower than death/explosion, while still
# making a confirmed multi-hit incident high risk.
SCHOOL_HARM_SEVERITY_WEIGHTS: dict[str, int] = {
    "霸凌": 60,
    "欺凌": 60,
    "校园暴力": 70,
    "殴打": 70,
    "扇耳光": 65,
    "被打": 60,
    "体罚": 55,
}

SCHOOL_HARM_FALLBACK_WEIGHTS: dict[str, int] = {
    "霸凌": 6,
    "欺凌": 6,
    "校园暴力": 7,
    "殴打": 7,
    "扇耳光": 7,
    "被打": 6,
    "体罚": 5,
}

LAW_ENFORCEMENT_HARM_KEYWORDS: frozenset[str] = frozenset(
    {
        "暴力执法",
        "执法打人",
        "执法殴打",
        "辅警殴打",
        "警察殴打",
        "被辅警打",
        "被警察打",
        "执法致伤",
        "暴力执法乱象",
    }
)

LAW_ENFORCEMENT_HARM_SEVERITY_WEIGHTS: dict[str, int] = {
    "暴力执法": 55,
    "执法打人": 70,
    "执法殴打": 70,
    "辅警殴打": 70,
    "警察殴打": 70,
    "被辅警打": 70,
    "被警察打": 70,
    "执法致伤": 80,
    "暴力执法乱象": 60,
}

LAW_ENFORCEMENT_HARM_FALLBACK_WEIGHTS: dict[str, int] = {
    "暴力执法": 5,
    "执法打人": 6,
    "执法殴打": 6,
    "辅警殴打": 7,
    "警察殴打": 7,
    "被辅警打": 7,
    "被警察打": 7,
    "执法致伤": 8,
    "暴力执法乱象": 6,
}

# These terms express a serious allegation or governance failure, but do not
# by themselves prove that physical harm occurred. They raise rule risk and
# negative sentiment without contributing to Severity.
LAW_ENFORCEMENT_CONTEXT_FALLBACK_WEIGHTS: dict[str, int] = {
    "包庇": 4,
    "置若罔闻": 4,
    "执法不公": 5,
    "司法不公": 5,
    "执法乱象": 5,
    "滥用职权": 6,
}

ALL_HARM_KEYWORDS: frozenset[str] = frozenset(
    {*SCHOOL_HARM_KEYWORDS, *LAW_ENFORCEMENT_HARM_KEYWORDS}
)

# A nearby prevention/education marker means the text is describing a
# policy, campaign, or prohibition rather than an incident.
_PREVENTION_MARKERS = (
    "反",
    "防范",
    "预防",
    "严禁",
    "禁止",
    "杜绝",
    "抵制",
    "拒绝",
    "避免",
    "防止",
    "制止",
    "打击",
    "规范",
    "加强",
    "宣传",
    "教育",
    "培训",
    "整治",
    "排查",
    "普及",
    "倡导",
)


def is_actual_harm_hit(text: str, keyword: str) -> bool:
    """Return whether a harm keyword describes an actual incident."""

    if not text:
        return False
    if keyword not in ALL_HARM_KEYWORDS:
        return keyword in text

    pattern = re.escape(keyword)
    if keyword == "扇耳光":
        pattern = r"扇[\u4e00-\u9fff]{0,6}耳光"

    for match in re.finditer(pattern, text):
        start = match.start()
        end = match.end()
        before = text[max(0, start - 8) : start]
        after = text[end : end + 8]
        compact_before = re.sub(r"[\s，。！？、；：:,.!?\"'“”‘’（）()]", "", before)
        compact_after = re.sub(r"[\s，。！？、；：:,.!?\"'“”‘’（）()]", "", after)
        if not any(compact_before.endswith(marker) for marker in _PREVENTION_MARKERS) and not any(
            compact_after.startswith(marker) for marker in _PREVENTION_MARKERS
        ):
            return True
    return False


def matches_harm_keyword(text: str, keyword: str) -> bool:
    """Match literal harm terms plus common Chinese insertions."""

    if not text:
        return False
    if keyword == "扇耳光":
        return re.search(r"扇[\u4e00-\u9fff]{0,6}耳光", text) is not None
    return keyword in text


def is_actual_school_harm_hit(text: str, keyword: str) -> bool:
    """Backward-compatible alias for the shared harm predicate."""

    return is_actual_harm_hit(text, keyword)


def matches_school_harm_keyword(text: str, keyword: str) -> bool:
    """Backward-compatible alias for the shared harm matcher."""

    return matches_harm_keyword(text, keyword)


def has_actual_harm_indicator(text: str, keywords: Iterable[str]) -> bool:
    """Shared AlertService positive-sentiment protection predicate."""

    value = text or ""
    for keyword in keywords:
        if keyword in ALL_HARM_KEYWORDS:
            if is_actual_harm_hit(value, keyword):
                return True
        elif keyword and keyword in value:
            return True
    return False
