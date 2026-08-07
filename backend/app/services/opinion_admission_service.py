"""Rule-based Opinion admission for Phase 1-B.

The service is intentionally small and deterministic: no DB access, no NLP
platform, and no LLM calls. It decides whether a standardized collector item is
valuable enough to become an Opinion.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from app.services.opinion_region_service import is_national_scope


def _hits(text: str, words: Iterable[str]) -> list[str]:
    seen: list[str] = []
    for word in words:
        w = (word or "").strip()
        if w and w in text and w not in seen:
            seen.append(w)
    return seen


def _clip_score(score: int) -> int:
    return max(0, min(100, score))


@dataclass(frozen=True)
class AdmissionResult:
    accepted: bool
    relevance_score: int
    content_type: str
    admission_reason: dict[str, Any]


class OpinionAdmissionService:
    """Pure rule-based admission service.

    Social posts (weibo_post, xhs_note, …) enter the content-scoring/classification
    path so their type and admission reason vary by content. Other sources are
    allowed by a compatibility default-allow policy.
    """

    # 进入「社交内容评分+分类」统一路径的 source_type 集合。
    # 微博、小红书同款处理；后续可扩展抖音等社交平台。
    SOCIAL_POST_TYPES = frozenset({"weibo_post", "xhs_note"})

    DEFAULT_REGION_WORDS = (
        "廊坊", "广阳", "安次", "固安", "永清", "香河", "大城", "文安", "大厂", "三河", "霸州",
    )
    SPECIFIC_PLACE_WORDS = (
        "小区", "社区", "村", "镇", "街道", "学校", "幼儿园", "医院", "工厂", "企业", "园区", "景区",
        "路", "桥", "站", "市场", "物业", "居民", "家长", "学生", "业主",
    )
    PUBLIC_AFFAIRS_WORDS = (
        "停水", "停电", "供暖", "物业", "收费", "交通", "拥堵", "施工", "教育", "学校", "医院",
        "社保", "医保", "工资", "欠薪", "环保", "污染", "食品安全", "燃气", "消防", "执法", "审批",
        "政务", "民生", "居民", "群众", "社区", "公共", "部门", "官方", "通报", "回应", "处置",
    )
    DEMAND_WORDS = (
        "投诉", "举报", "反映", "维权", "求助", "希望处理", "谁来管", "没人管", "解决", "讨说法",
        "曝光", "质疑", "咨询", "怎么办", "协调", "赔偿", "起诉", "拖欠", "乱收费",
    )
    CONSULTATION_WORDS = ("咨询", "求助", "怎么办", "如何办理", "怎么处理", "哪里办")
    RISK_WORDS = (
        "事故", "火灾", "爆炸", "坍塌", "诈骗", "冲突", "打架", "伤亡", "受伤", "死亡", "失联",
        "中毒", "污染", "泄漏", "堵路", "聚集", "上访", "舆情", "安全隐患", "违法", "腐败",
    )
    ENTERTAINMENT_WORDS = (
        "男模", "女模", "帅哥", "美女", "榜一", "好帅", "好美", "明星", "演唱会", "追星", "饭圈",
        "写真", "网红", "娱乐", "八卦", "cp", "应援",
    )
    ADVERTISING_WORDS = (
        "优惠", "团购", "促销", "招商", "加盟", "电话", "微信", "私信", "下单", "包邮", "直播间",
        "现货", "厂家", "推广", "广告", "租房", "招聘", "低价", "特价", "秒杀",
    )
    LIFESTYLE_WORDS = (
        "美食", "吃什么", "旅游", "打卡", "探店", "逛街", "拍照", "好吃", "攻略", "推荐", "民宿",
        "咖啡", "夜市", "周末去哪", "露营", "穿搭",
    )

    def evaluate(
        self,
        item: dict[str, Any],
        *,
        region_keywords: Iterable[str] | None = None,
        topic_keywords: Iterable[str] | None = None,
        collector_name: str = "",
        source_scope_codes: Iterable[str] | None = None,
        national_source: bool | None = None,
        region_hits: Iterable[Any] | None = None,
        collection_mode: str | None = None,
    ) -> AdmissionResult:
        source_type = item.get("source_type")
        source = str(item.get("source") or collector_name or "")
        region_hit_list = list(region_hits or [])
        if national_source is not None:
            is_national = bool(national_source)
        elif source_scope_codes is not None:
            is_national = is_national_scope(source_scope_codes)
        else:
            is_national = False

        if source_type == "weibo_comment":
            return AdmissionResult(
                accepted=False,
                relevance_score=0,
                content_type="irrelevant",
                admission_reason={
                    "decision": "rejected",
                    "policy": "weibo_comment_not_opinion_subject",
                },
            )

        if source_type not in self.SOCIAL_POST_TYPES:
            # National-Mode-4：显式 national 模式不再要求地域相关性。
            # 采集阶段已完成 topic_only 过滤（无主题稿已被 collector 前置拦截），
            # 因此到达此处的 national 条目视为已通过主题相关性，直接准入。
            # 仅 collection_mode=="national" 走此分支；regional / 隐式 national 路径不变。
            if collection_mode == "national":
                content_type = self._default_content_type(source, collector_name)
                return AdmissionResult(
                    accepted=True,
                    relevance_score=100,
                    content_type=content_type,
                    admission_reason={
                        "decision": "accepted",
                        "policy": "national_mode_topic_accepted",
                        "source": source,
                        "region_hits": region_hit_list,
                    },
                )
            if is_national and not region_hit_list:
                return AdmissionResult(
                    accepted=False,
                    relevance_score=0,
                    content_type="irrelevant",
                    admission_reason={
                        "decision": "rejected",
                        "policy": "national_source_requires_region_relevance",
                        "source": source,
                        "region_hits": [],
                    },
                )
            content_type = self._default_content_type(source, collector_name)
            return AdmissionResult(
                accepted=True,
                relevance_score=100,
                content_type=content_type,
                admission_reason={
                    "decision": "accepted",
                    "policy": (
                        "national_source_region_relevance"
                        if is_national
                        else "default_allow_non_weibo"
                    ),
                    "source": source,
                    "region_hits": region_hit_list,
                },
            )

        title = str(item.get("title") or "")
        content = str(item.get("content") or "")
        text = f"{title} {content}".strip()
        if not text:
            return AdmissionResult(False, 0, "irrelevant", {"decision": "rejected", "reason": "empty_text"})

        regions = tuple(region_keywords or ()) or self.DEFAULT_REGION_WORDS
        topics = tuple(topic_keywords or ())
        region_hits = _hits(text, regions)
        topic_hits = _hits(text, topics)
        place_hits = _hits(text, self.SPECIFIC_PLACE_WORDS)
        public_hits = _hits(text, self.PUBLIC_AFFAIRS_WORDS)
        for hit in topic_hits:
            if hit not in public_hits:
                public_hits.append(hit)
        demand_hits = _hits(text, self.DEMAND_WORDS)
        consult_hits = _hits(text, self.CONSULTATION_WORDS)
        risk_hits = _hits(text, self.RISK_WORDS)
        entertainment_hits = _hits(text, self.ENTERTAINMENT_WORDS)
        advertising_hits = _hits(text, self.ADVERTISING_WORDS)
        lifestyle_hits = _hits(text, self.LIFESTYLE_WORDS)

        score = 10
        score_parts: dict[str, int] = {"text_valid": 10}
        if region_hits:
            score += 25
            score_parts["region"] = 25
        if place_hits:
            score += 15
            score_parts["specific_place"] = 15
        if public_hits:
            score += 15
            score_parts["public_affairs"] = 15
        if demand_hits:
            score += 25
            score_parts["demand"] = 25
        if risk_hits:
            score += 30
            score_parts["risk_event"] = 30

        engagement_bonus = self._engagement_bonus(item.get("engagement"))
        if engagement_bonus:
            score += engagement_bonus
            score_parts["engagement"] = engagement_bonus

        if entertainment_hits:
            score -= 40
            score_parts["entertainment"] = -40
        if advertising_hits:
            score -= 50
            score_parts["advertising"] = -50
        if lifestyle_hits:
            score -= 30
            score_parts["lifestyle"] = -30

        has_public_signal = bool(place_hits or public_hits or demand_hits or risk_hits)
        if region_hits and not has_public_signal:
            score = min(score, 35)
            score_parts["pure_region_cap"] = 35

        final_score = _clip_score(score)
        accepted = final_score >= 40
        content_type = self._classify_content_type(
            accepted=accepted,
            demand_hits=demand_hits,
            consult_hits=consult_hits,
            risk_hits=risk_hits,
            public_hits=public_hits,
            advertising_hits=advertising_hits,
            entertainment_hits=entertainment_hits,
            lifestyle_hits=lifestyle_hits,
        )

        return AdmissionResult(
            accepted=accepted,
            relevance_score=final_score,
            content_type=content_type,
            admission_reason={
                "decision": "accepted" if accepted else "rejected",
                "region_hits": region_hits,
                "place_hits": place_hits,
                "public_hits": public_hits,
                "demand_hits": demand_hits,
                "risk_hits": risk_hits,
                "noise_hits": {
                    "entertainment": entertainment_hits,
                    "advertising": advertising_hits,
                    "lifestyle": lifestyle_hits,
                },
                "score_parts": score_parts,
            },
        )

    def _default_content_type(self, source: str, collector_name: str) -> str:
        text = f"{source} {collector_name}"
        if any(word in text for word in ("政府", "政务", "公告", "政策", "管委会")):
            return "policy"
        return "news"

    def _engagement_bonus(self, engagement: Any) -> int:
        if not isinstance(engagement, dict):
            return 0
        total = 0
        # 互动量包含微博的 likes/comments/reposts，以及小红书的 collections（收藏）。
        for key in ("likes", "comments", "reposts", "collections"):
            try:
                total += int(engagement.get(key) or 0)
            except (TypeError, ValueError):
                continue
        if total >= 500:
            return 15
        if total >= 100:
            return 10
        if total >= 20:
            return 5
        return 0

    def _classify_content_type(
        self,
        *,
        accepted: bool,
        demand_hits: list[str],
        consult_hits: list[str],
        risk_hits: list[str],
        public_hits: list[str],
        advertising_hits: list[str],
        entertainment_hits: list[str],
        lifestyle_hits: list[str],
    ) -> str:
        if not accepted:
            if advertising_hits:
                return "advertising"
            if entertainment_hits:
                return "entertainment"
            return "irrelevant"
        if risk_hits:
            return "risk_event"
        if consult_hits and not demand_hits:
            return "consultation"
        if demand_hits:
            return "complaint"
        if public_hits:
            return "public_affairs"
        if advertising_hits:
            return "advertising"
        if entertainment_hits or lifestyle_hits:
            return "entertainment"
        return "public_affairs"
