"""Rule-based region decision for collected Opinion items.

The collector's ``scope_region_codes`` describes source coverage only.  This
service decides the factual monitoring region for each standardized item using
lightweight text hits and existing Region rows.  It does not call external
services and does not mutate collector parsing behavior.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from sqlalchemy.orm import Session

from app.models.region import Region

LANGFANG_CITY_CODE = "131000"

LANGFANG_REGION_ALIASES: dict[str, tuple[str, ...]] = {
    "131000": ("廊坊", "廊坊市"),
    "131002": ("安次", "安次区"),
    "131003": ("广阳", "广阳区"),
    "131022": ("固安", "固安县"),
    "131023": ("永清", "永清县"),
    "131024": ("香河", "香河县"),
    "131025": ("大城", "大城县"),
    "131026": ("文安", "文安县"),
    "131028": ("大厂", "大厂县", "大厂回族自治县"),
    "131081": ("霸州", "霸州市"),
    "131082": ("三河", "三河市"),
}

NEGATED_REGION_PREFIXES = ("没有", "无", "不涉及", "未涉及", "并非")
NEGATED_REGION_SUFFIXES = ("无关", "无直接关系")


@dataclass(frozen=True)
class RegionDecision:
    region_id: int | None
    region_hits: list[dict[str, str]]
    decision: str
    reason: str
    national_source: bool

    @property
    def accepted(self) -> bool:
        return self.decision.startswith("accepted")

    def as_reason(self) -> dict[str, Any]:
        return {
            "decision": self.decision,
            "reason": self.reason,
            "region_id": self.region_id,
            "region_hits": self.region_hits,
            "national_source": self.national_source,
        }


def normalize_scope_codes(scope_region_codes: Iterable[str] | None) -> list[str]:
    if not scope_region_codes:
        return []
    codes: list[str] = []
    for raw in scope_region_codes:
        value = str(raw or "").strip()
        if not value or value.upper() == "ALL":
            continue
        codes.append(value)
    return codes


def is_national_scope(scope_region_codes: Iterable[str] | None) -> bool:
    return not normalize_scope_codes(scope_region_codes)


class OpinionRegionService:
    """Resolve an item's factual monitoring region with deterministic rules."""

    def decide(
        self,
        db: Session,
        item: dict[str, Any],
        *,
        scope_region_codes: Iterable[str] | None = None,
    ) -> RegionDecision:
        title = str(item.get("title") or "")
        content = str(item.get("content") or "")
        text = f"{title} {content}".strip()
        scope_codes = normalize_scope_codes(scope_region_codes)
        national = not scope_codes
        hits = self._region_hits(text)

        if hits:
            hit_codes = {h["code"] for h in hits}
            county_codes = sorted(code for code in hit_codes if code != LANGFANG_CITY_CODE)
            if len(county_codes) == 1:
                region = self._region_by_code(db, county_codes[0])
                if region is not None:
                    return RegionDecision(
                        region.id,
                        hits,
                        "accepted_specific_region_hit",
                        "single_specific_county_hit",
                        national,
                    )
            if len(county_codes) >= 2:
                region = self._region_by_code(db, LANGFANG_CITY_CODE)
                if region is not None:
                    return RegionDecision(
                        region.id,
                        hits,
                        "accepted_multiple_county_hits",
                        "multiple_same-level_counties_fallback_city",
                        national,
                    )
            region = self._region_by_code(db, LANGFANG_CITY_CODE)
            if region is not None:
                return RegionDecision(
                    region.id,
                    hits,
                    "accepted_city_region_hit",
                    "langfang_city_hit",
                    national,
                )

        if national:
            return RegionDecision(
                None,
                hits,
                "rejected_no_monitoring_region_hit",
                "national_source_requires_explicit_langfang_region_hit",
                True,
            )

        default_region = self._default_scope_region(db, scope_codes)
        if default_region is None:
            return RegionDecision(
                None,
                hits,
                "rejected_scope_region_not_found",
                "scope_region_codes_not_found_in_regions",
                False,
            )
        return RegionDecision(
            default_region.id,
            hits,
            "accepted_scope_default",
            "local_or_regional_source_uses_scope_default",
            False,
        )

    def _region_hits(self, text: str) -> list[dict[str, str]]:
        seen: set[tuple[str, str]] = set()
        hits: list[dict[str, str]] = []
        for code, words in LANGFANG_REGION_ALIASES.items():
            for word in words:
                if (
                    word
                    and word in text
                    and (code, word) not in seen
                    and not self._is_negated_hit(text, word)
                ):
                    seen.add((code, word))
                    hits.append({"code": code, "word": word})
        return hits

    def _is_negated_hit(self, text: str, word: str) -> bool:
        start = text.find(word)
        found = False
        while start >= 0:
            found = True
            before = text[max(0, start - 8):start]
            after = text[start + len(word): start + len(word) + 8]
            negated = any(token in before for token in NEGATED_REGION_PREFIXES) or any(
                token in after for token in NEGATED_REGION_SUFFIXES
            )
            if not negated:
                return False
            start = text.find(word, start + len(word))
        return found

    def _default_scope_region(self, db: Session, scope_codes: list[str]) -> Region | None:
        for code in sorted(scope_codes, key=len, reverse=True):
            region = self._region_by_code(db, code)
            if region is not None:
                return region
        return None

    def _region_by_code(self, db: Session, code: str) -> Region | None:
        return db.query(Region).filter(Region.code == code).first()
