"""Deterministic Event topic classification.

This module intentionally stays small and rule-based: no external NLP platform,
no AI calls, and no schema changes.  It derives Event.topic_category from
existing Opinion fields and text.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable

from app.models.opinion import Opinion

TOPIC_CATEGORIES: tuple[str, ...] = (
    "livelihood",
    "traffic",
    "education",
    "healthcare",
    "environment",
    "safety",
    "market",
    "gov_service",
    "social_security",
    "public_emergency",
    "other",
)

RISK_CATEGORY_TOPIC_MAP: dict[str, str] = {
    "safety_accident": "safety",
    "public_emergency": "public_emergency",
    "social_security": "social_security",
    "political": "gov_service",
    "gov_service": "gov_service",
    "market": "market",
    "environment": "environment",
    "traffic": "traffic",
    "education": "education",
    "healthcare": "healthcare",
}

TOPIC_KEYWORDS: dict[str, tuple[str, ...]] = {
    "traffic": (
        "交通", "道路", "公路", "公交", "客运", "出租车", "停车", "拥堵", "堵车",
        "红绿灯", "路口", "桥梁", "事故车辆", "追尾", "货车", "校车",
    ),
    "education": (
        "学校", "学生", "家长", "教师", "老师", "幼儿园", "小学", "中学", "高中",
        "校园", "招生", "学费", "补课", "培训", "收费问题",
    ),
    "healthcare": (
        "医院", "医疗", "医保", "医生", "护士", "门诊", "住院", "患者", "药品",
        "卫生院", "疾控", "看病", "诊疗", "疫苗",
    ),
    "environment": (
        "环保", "污染", "污水", "废气", "扬尘", "噪声", "噪音", "异味", "垃圾",
        "排放", "空气质量", "河道", "黑臭水体",
    ),
    "safety": (
        "安全", "治安", "诈骗", "打架", "斗殴", "盗窃", "刑事", "涉警", "消防",
        "隐患", "燃气", "电动车", "生产安全",
    ),
    "market": (
        "市场", "商家", "消费", "消费者", "价格", "涨价", "收费", "乱收费",
        "食品安全", "假冒", "质量", "合同", "退款", "物业费",
    ),
    "gov_service": (
        "政务", "审批", "办事", "窗口", "证件", "手续", "执法", "城管", "通报",
        "回应", "政策", "公告", "公示", "热线", "部门", "办理",
    ),
    "social_security": (
        "社保", "医保报销", "养老保险", "失业保险", "工伤保险", "低保", "救助",
        "养老金", "保障房", "公积金",
    ),
    "public_emergency": (
        "突发", "火灾", "爆炸", "坍塌", "洪水", "地震", "中毒", "伤亡", "死亡",
        "失联", "救援", "应急", "泄漏",
    ),
    "livelihood": (
        "民生", "居民", "群众", "社区", "小区", "物业", "供暖", "停水", "停电",
        "供水", "供电", "工资", "欠薪", "征地", "拆迁", "住房",
    ),
}

CONTENT_TYPE_TOPIC_HINTS: dict[str, str] = {
    "consultation": "gov_service",
    "public_affairs": "livelihood",
    "policy": "gov_service",
}


@dataclass(frozen=True)
class TopicResult:
    topic: str
    scores: dict[str, int]
    reason: str


def _clamp_risk_score(score: int | None) -> int:
    return max(0, min(100, int(score or 0)))


def _effective_time(op: Opinion) -> datetime:
    return op.publish_time or op.created_at or datetime.min


class EventTopicService:
    """Classify Opinion/Event topics using existing fields and text."""

    def classify_opinion(self, opinion: Opinion) -> TopicResult:
        scores: Counter[str] = Counter()
        reasons: list[str] = []

        risk_category = (getattr(opinion, "risk_category", None) or "").strip()
        risk_topic = RISK_CATEGORY_TOPIC_MAP.get(risk_category)
        if risk_topic and risk_topic != "other":
            scores[risk_topic] += 5
            reasons.append(f"risk_category:{risk_category}")

        text = f"{getattr(opinion, 'title', '') or ''} {getattr(opinion, 'content', '') or ''}"
        for topic, words in TOPIC_KEYWORDS.items():
            hits = [word for word in words if word in text]
            if hits:
                scores[topic] += len(hits) * 2
                reasons.append(f"{topic}:{','.join(hits[:5])}")

        content_type = (getattr(opinion, "content_type", None) or "").strip()
        hint = CONTENT_TYPE_TOPIC_HINTS.get(content_type)
        if hint:
            scores[hint] += 1
            reasons.append(f"content_type:{content_type}")

        if not scores:
            return TopicResult("other", {}, "no_topic_signal")
        topic, score = self._pick_topic(scores)
        if score <= 0:
            return TopicResult("other", dict(scores), "non_positive_topic_score")
        return TopicResult(topic, dict(scores), ";".join(reasons))

    def classify_event(self, opinions: Iterable[Opinion]) -> TopicResult:
        rows = list(opinions)
        if not rows:
            return TopicResult("other", {}, "no_opinions")

        total: Counter[str] = Counter()
        per_opinion: dict[int, str] = {}
        for op in rows:
            result = self.classify_opinion(op)
            per_opinion[getattr(op, "id", 0) or 0] = result.topic
            for topic, score in result.scores.items():
                total[topic] += score

        if not total:
            return TopicResult("other", {}, "no_topic_signal")

        best_score = max(total.values())
        winners = [topic for topic, score in total.items() if score == best_score]
        if len(winners) == 1:
            return TopicResult(winners[0], dict(total), "highest_accumulated_score")

        rep = sorted(
            rows,
            key=lambda op: (
                -_clamp_risk_score(getattr(op, "risk_score", 0)),
                _effective_time(op),
                getattr(op, "id", 0) or 0,
            ),
        )[0]
        rep_topic = per_opinion.get(getattr(rep, "id", 0) or 0, "other")
        if rep_topic in winners:
            return TopicResult(rep_topic, dict(total), "tie_break_by_top_risk_opinion")
        return TopicResult(self._topic_order(winners)[0], dict(total), "tie_break_by_topic_order")

    def _pick_topic(self, scores: Counter[str]) -> tuple[str, int]:
        best_score = max(scores.values())
        winners = [topic for topic, score in scores.items() if score == best_score]
        return self._topic_order(winners)[0], best_score

    def _topic_order(self, topics: Iterable[str]) -> list[str]:
        order = {topic: idx for idx, topic in enumerate(TOPIC_CATEGORIES)}
        return sorted(topics, key=lambda topic: order.get(topic, 999))
