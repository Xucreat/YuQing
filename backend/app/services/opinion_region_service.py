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

from app.constants.region import NATIONAL_REGION_CODE
from app.models.region import Region
from app.services.keyword_filter_service import KeywordFilterService

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


def resolve_national_region(db: Session) -> Region:
    """Return the system-level "全国" sentinel Region (code = NATIONAL_REGION_CODE).

    National-Mode-2 数据准备插入 code='000000' name='全国' 的哨兵 Region 行；
    本函数为其唯一、只读的查询入口，供后续 National-Mode-4+ 准入逻辑作为
    ``Opinion.region_id``（NOT NULL）的合法「全国兜底」承载来源。

    行为约束（与 National-Mode-2 约束一致）：
      - 纯只读查询，**绝不自动创建**该数据行；
      - 若哨兵 Region 缺失，抛 ``RuntimeError``，让调用方「快速失败」而非静默写入
        NULL 或脏数据（避免破坏 Event/Risk 聚合链路）。
    """
    region = db.query(Region).filter(Region.code == NATIONAL_REGION_CODE).first()
    if region is None:
        raise RuntimeError(
            f"系统级「全国」哨兵 Region 不存在 (code={NATIONAL_REGION_CODE!r})，"
            f"请先执行 National-Mode-2 数据准备（插入哨兵 Region 行）。"
        )
    return region


class OpinionRegionService:
    """Resolve an item's factual monitoring region with deterministic rules."""

    def decide(
        self,
        db: Session,
        item: dict[str, Any],
        *,
        scope_region_codes: Iterable[str] | None = None,
        collection_mode: str | None = None,
    ) -> RegionDecision:
        title = str(item.get("title") or "")
        content = str(item.get("content") or "")
        text = f"{title} {content}".strip()
        scope_codes = normalize_scope_codes(scope_region_codes)
        # National-Mode-4：collection_mode 显式优先；缺省回退「空 scope 推断」
        # （向后兼容：未显式声明 national 的源保持原有隐式推断行为）。
        national = (collection_mode == "national") or (not scope_codes)
        hits = self._region_hits(text, is_local_source=not national)

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
            # National-Mode-4：显式 national 模式（collection_mode=="national"）下，
            # 无地域命中时不再拒绝，而是使用「全国」哨兵 Region 作为合法 region_id 兜底，
            # 从而在不放开 Opinion.region_id NOT NULL 的前提下完成全国主题稿入库。
            # 隐式 national（仅空 scope、未显式声明 mode）保持原有拒绝行为，生产零变化。
            if collection_mode == "national":
                sentinel = resolve_national_region(db)
                return RegionDecision(
                    sentinel.id,
                    hits,
                    "accepted_national_sentinel",
                    "national_mode_no_region_hit_uses_sentinel",
                    True,
                )
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

    def _region_hits(self, text: str, *, is_local_source: bool = False) -> list[dict[str, str]]:
        seen: set[tuple[str, str]] = set()
        hits: list[dict[str, str]] = []
        kf = KeywordFilterService.default()
        for code, words in LANGFANG_REGION_ALIASES.items():
            for word in words:
                if (
                    word
                    and word in text
                    and (code, word) not in seen
                    and not self._is_negated_hit(text, word)
                ):
                    # Phase X：131028「大厂」裸别名需经语义过滤，避免互联网「大厂」
                    # 被错误绑定大厂回族自治县(131028)标签（"大厂县"/"大厂回族自治县"
                    # 为强地域锚点，无需过滤）。
                    if code == "131028" and word == "大厂":
                        if not kf.is_valid_match("大厂", text, is_local_source=is_local_source):
                            continue
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
