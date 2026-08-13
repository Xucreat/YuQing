"""Explainable, non-persistent event risk shadow calculation."""
from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime


def _score(value: object) -> float:
    try:
        return max(0.0, min(100.0, float(value or 0)))
    except (TypeError, ValueError):
        return 0.0


class EventRiskShadowService:
    score_version = "event-risk-shadow-v1"

    @classmethod
    def calculate(cls, event, opinions: Iterable) -> dict:
        rows = list(opinions)
        count = len(rows)
        risks = [_score(getattr(row, "current_risk_score", getattr(row, "risk_score", 0))) for row in rows]
        content_risk = sum(risks) / count if count else 0.0
        high_risk_count = sum(1 for value in risks if value >= 70)
        # A single high-risk opinion contributes evidence, but cannot alone make
        # an event high risk: volume and corroboration remain separate factors.
        volume = min(100.0, count * 10.0)
        times = [getattr(row, "publish_time", None) for row in rows]
        times = [value for value in times if isinstance(value, datetime)]
        growth = cls._growth_score(times)
        region_id = getattr(event, "region_id", None)
        locality = (sum(1 for row in rows if getattr(row, "region_id", None) == region_id) / count * 100.0) if count and region_id else 0.0
        event_type = cls._event_type_score(getattr(event, "topic_category", None))
        factors = [
            {"factor": "content_risk", "value": round(content_risk, 2), "description": f"存在 {high_risk_count} 条高风险内容，关联内容平均风险分 {round(content_risk)}" if count else "暂无关联内容"},
            {"factor": "volume", "value": round(volume, 2), "description": f"事件包含 {count} 条内容"},
            {"factor": "growth", "value": round(growth, 2), "description": "近期内容量较前期上升" if growth >= 60 else "近期内容量变化有限"},
            {"factor": "locality", "value": round(locality, 2), "description": "内容与事件所属区域一致性" if region_id else "事件未设置所属区域"},
            {"factor": "event_type", "value": round(event_type, 2), "description": f"事件主题类型：{getattr(event, 'topic_category', None) or '未分类'}"},
        ]
        score = round(
            content_risk * 0.35
            + volume * 0.20
            + growth * 0.20
            + locality * 0.15
            + event_type * 0.10
        )
        level = "high" if score >= 70 else "medium" if score >= 40 else "low"
        return {"score": max(0, min(100, score)), "level": level, "factors": factors, "score_version": cls.score_version}

    compute = calculate

    @staticmethod
    def _growth_score(times: list[datetime]) -> float:
        if len(times) < 2:
            return 0.0
        ordered = sorted(times)
        midpoint = ordered[0] + (ordered[-1] - ordered[0]) / 2
        first = sum(1 for value in ordered if value <= midpoint)
        second = len(ordered) - first
        if first == 0:
            return 100.0
        return min(100.0, max(0.0, second / first * 100.0))

    @staticmethod
    def _event_type_score(topic: str | None) -> float:
        return 80.0 if topic in {"public_emergency", "safety", "social_security"} else 45.0 if topic else 20.0
