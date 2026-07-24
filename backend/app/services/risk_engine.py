"""RiskEngine —— Risk Model V2 Phase 2-A 独立风险精炼层。

设计定位（与既有约束一致）：
  - 纯函数、无数据库访问、无数据库写入；severity 词典经构造参数注入
    （与 RuleFallbackProvider.__init__(keywords=...) 同构），可单测、可注入。
  - 不替换 RuleFallbackProvider：RuleFallbackProvider 负责「规则风险评分」
    （risk_score 基础），RiskEngine 在其后做「Severity / EventState /
    ResolutionFlag / 最终风险分」的精炼，二者职责分离。
  - 返回独立结果对象 RiskRefinement；**不修改 AIAnalysisResult**
    （其 model_config={"extra":"forbid"}，且 DeepSeekProvider 经它校验，
    增加字段会击穿 DeepSeek 路径）。
  - 风险内核不可被情感 / 事件状态压制：SeverityFloor 保证重大真实事件
    即使「已解决 / 正面报道」也保留高危 / critical。

计算口径（增量演进，不推翻现有系统）：
  BASE_RISK        = 20                       # 保留底座，无危害词文章不跌到 0
  Severity         = min( Σ(severity_weight of hit 真实危害词), 100 )
  StateFactor      = {occurred:1.0, notice:0.85, deploy:0.70, prevent:0.55, resolved:0.35}
  SeverityAdj      = min(Severity * StateFactor, 100)
  SentimentAdj     = (sentiment=='positive') ? min(0.25*(100-Severity), 25) : 0
  SeverityFloor    = Severity>=70 ? 70 : (Severity>=50 ? 50 : 0)   # 不可抑制内核
  final_score      = clamp( max(SeverityAdj - SentimentAdj, SeverityFloor, BASE_RISK), 0, 100 )
  resolution_flag  = (event_state == 'resolved')
  severity_score   = Severity（供 AlertService 派生 critical 档）
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------
BASE_RISK = 20  # 与 fallback.py 的 BASE_RISK 同源，保留分数底座

# Phase 2-A.1：风险模型版本号（随 opinion 写回，标记该条评分所用模型版本）。
# 仅当评分公式/词典语义发生变化时递增；解释性字段的增加不改变评分，不递增。
RISK_MODEL_VERSION = "risk-v2.0"

# 真实危害指标词 → 严重度权重（与 alert_service.HARM_INDICATOR_KEYWORDS 同源）。
# 语境词（投诉/舆情/维权/群体）不入此表 → Severity 只计真实风险词。
# 这是「无数据库 / 测试 / 演示」路径的 fallback；生产可由 keywords 表
# severity_weight 列覆盖（见 keyword_service.get_severity_keywords）。
DEFAULT_SEVERITY_KEYWORDS: Dict[str, int] = {
    "火灾": 80,
    "爆炸": 90,
    "伤亡": 90,
    "死亡": 90,
    "事故": 60,
    "冲突": 50,
    "上访": 50,
    "谣言": 45,
    "诈骗": 50,
    "腐败": 50,
    "贪污": 50,
    "涉警": 55,
}

# 事件状态单枚举 + 触发短语词典（可配置；Phase 2 后期可入库为 keywords type='state'）。
# 多状态共存时取「最缓和」者：resolved > prevent > deploy > notice > occurred。
STATE_OCCURRED = "occurred"
STATE_NOTICE = "notice"
STATE_DEPLOY = "deploy"
STATE_PREVENT = "prevent"
STATE_RESOLVED = "resolved"

STATE_PHRASES: Dict[str, List[str]] = {
    STATE_OCCURRED: ["发生", "出现", "造成", "致", "引发", "突发", "遇难"],
    STATE_NOTICE: ["通报", "公布", "发布", "回应", "表态", "致歉"],
    STATE_DEPLOY: ["部署", "安排", "落实", "实施", "推进", "开展"],
    STATE_PREVENT: ["防范", "预防", "演练", "预案", "排查", "整治"],
    STATE_RESOLVED: ["解决", "妥善处理", "办结", "整改完成", "化解", "善后", "问责到位"],
}

# 状态优先级（从高到低 = 从最缓和到最严重），决定多状态共存时的胜出者。
STATE_PRIORITY: List[str] = [
    STATE_RESOLVED,
    STATE_PREVENT,
    STATE_DEPLOY,
    STATE_NOTICE,
    STATE_OCCURRED,
]

# 状态折减因子（StateFactor）。
STATE_FACTORS: Dict[str, float] = {
    STATE_OCCURRED: 1.0,
    STATE_NOTICE: 0.85,
    STATE_DEPLOY: 0.70,
    STATE_PREVENT: 0.55,
    STATE_RESOLVED: 0.35,
}

# 所有合法状态值（供模型 CheckConstraint 与校验复用）。
VALID_STATES: frozenset = frozenset(STATE_PHRASES.keys())

# ---------------------------------------------------------------------------
# Phase 2-B.2：风险分类（纯解释性标签，不参与评分）
# ---------------------------------------------------------------------------
# 将已命中的 severity_keywords 映射到风险分类。与 DEFAULT_SEVERITY_KEYWORDS
# 同源——分类词典仅读取词名（不读 weight），不影响评分。
# 多分类命中时：第一优先级 = severity 贡献最高；同分时按 CATEGORY_PRIORITY 决胜。
CATEGORY_OTHER = "other"
RISK_CATEGORY_MAP: Dict[str, str] = {
    "火灾": "safety_accident",
    "爆炸": "safety_accident",
    "伤亡": "safety_accident",
    "死亡": "safety_accident",
    "事故": "safety_accident",
    "冲突": "social_security",
    "涉警": "social_security",
    "诈骗": "social_security",
    "上访": "political",
    "谣言": "political",
    "腐败": "political",
    "贪污": "political",
}
# 同分决胜优先级（从高到低）
CATEGORY_PRIORITY: List[str] = [
    "safety_accident",
    "political",
    "social_security",
]


@dataclass
class RiskRefinement:
    """RiskEngine.refine() 的独立返回对象（不进入 AIAnalysisResult）。"""

    severity_score: int       # 真实危害严重度（0-100），供 critical 档派生
    event_state: str          # 单枚举状态
    resolution_flag: bool     # 是否「已解决」
    final_risk_score: int     # 精炼后的最终风险分（写回 opinion.risk_score）
    # ===== Phase 2-A.1：风险解释字段（仅解释，不参与评分）=====
    # 结构：{"severity": [{"keyword": "爆炸", "score": 90}, ...],
    #        "event_state": "occurred", "resolution_flag": false}
    # 不含内部算法调整过程（无 adjustments），可直接序列化为 JSONB。
    risk_factors: Dict[str, Any] = field(default_factory=dict)
    # ===== Phase 2-B.2：风险分类（纯解释性标签，不参与评分）=====
    # 由已收集的 severity_hits 派生，在所有评分变量计算完成后生成。
    # 值域：safety_accident / social_security / political / other
    risk_category: str = CATEGORY_OTHER


def _detect_state(text: str) -> str:
    """单枚举状态判定：命中多状态时取最缓和者；无命中默认 occurred。"""
    if not text:
        return STATE_OCCURRED
    matched = set()
    for state, phrases in STATE_PHRASES.items():
        for ph in phrases:
            if ph and ph in text:
                matched.add(state)
                break
    if not matched:
        return STATE_OCCURRED
    for state in STATE_PRIORITY:
        if state in matched:
            return state
    return STATE_OCCURRED


class RiskEngine:
    """风险精炼引擎（Phase 2-A）：Severity / EventState / ResolutionFlag / 最终风险分。

    纯函数、无 DB 依赖。severity_keywords 经构造注入：
      {harm_word: severity_weight, ...}
    缺省使用 DEFAULT_SEVERITY_KEYWORDS（内置 fallback），保证零回归与确定性。
    """

    def __init__(
        self, severity_keywords: Optional[Dict[str, int]] = None
    ) -> None:
        # 注入词表与内置 DEFAULT 合并：注入项覆盖同名默认，未注入的真实危害词
        # 仍保留默认权重（偏安全的设计，部分注入也能正确工作）。
        self.severity_keywords: Dict[str, int] = {
            **DEFAULT_SEVERITY_KEYWORDS,
            **(severity_keywords or {}),
        }

    def refine(self, title: str, content: str, sentiment: str) -> RiskRefinement:
        """输入原始标题/正文/情感，输出精炼风险结果。

        title/content 为原始文本（不含「标题：/正文：」前缀）；
        sentiment 取自 RuleFallbackProvider 的 AIAnalysisResult.sentiment。
        """
        text = f"{title or ''}\n{content or ''}"

        # 1) Severity：仅累加真实危害词的 severity_weight
        #    Phase 2-A.1：并行收集命中词作为解释因子（不影响求和结果）。
        severity = 0
        severity_hits: List[Dict[str, Any]] = []
        for word, weight in self.severity_keywords.items():
            if word and word in text:
                severity += weight
                severity_hits.append({"keyword": word, "score": weight})
        severity = min(severity, 100)

        # 2) Event State：单枚举（取最缓和）
        state = _detect_state(text)
        state_factor = STATE_FACTORS[state]

        # 3) Severity 经 StateFactor 折减
        severity_adj = min(severity * state_factor, 100.0)

        # 4) 正面情感折减（仅当真实危害较低时生效；重大事件由 Floor 兜底）
        sentiment_adj = (
            min(0.25 * (100 - severity), 25.0) if sentiment == "positive" else 0.0
        )

        # 5) SeverityFloor：风险内核不可被情感/状态压制
        #    Severity>=70（伤亡/死亡/爆炸等）→ 保底 70；50-69 → 保底 50；否则 0
        severity_floor = 70 if severity >= 70 else (50 if severity >= 50 else 0)

        # 6) 最终分：取「折减后 / Floor / 底座」三者最大，并夹在 [0,100]
        final = max(severity_adj - sentiment_adj, severity_floor, BASE_RISK)
        final = max(0, min(100, int(round(final))))

        resolution_flag = state == STATE_RESOLVED

        # Phase 2-A.1：风险解释因子（仅解释，不参与评分；无 adjustments 过程记录）。
        risk_factors: Dict[str, Any] = {
            "severity": severity_hits,
            "event_state": state,
            "resolution_flag": resolution_flag,
        }

        # Phase 2-B.2：风险分类（纯解释性标签，不参与评分）。
        # 在所有评分变量计算完成后，从已收集的 severity_hits 派生。
        # 第一优先级：severity 贡献最高的分类；同分时按 CATEGORY_PRIORITY 决胜。
        cat_scores: Dict[str, int] = {}
        for hit in severity_hits:
            cat = RISK_CATEGORY_MAP.get(hit.get("keyword", ""), CATEGORY_OTHER)
            cat_scores[cat] = cat_scores.get(cat, 0) + hit.get("score", 0)
        if cat_scores:
            max_score = max(cat_scores.values())
            top_cats = [c for c, s in cat_scores.items() if s == max_score and c != CATEGORY_OTHER]
            if not top_cats:
                # 最高分仅来自 other（不应发生，但防御性处理）
                risk_category = CATEGORY_OTHER
            elif len(top_cats) == 1:
                risk_category = top_cats[0]
            else:
                # 同分决胜：按 CATEGORY_PRIORITY 顺序取第一个
                risk_category = next(
                    (c for c in CATEGORY_PRIORITY if c in top_cats), top_cats[0]
                )
        else:
            risk_category = CATEGORY_OTHER

        return RiskRefinement(
            severity_score=int(severity),
            event_state=state,
            resolution_flag=resolution_flag,
            final_risk_score=final,
            risk_factors=risk_factors,
            risk_category=risk_category,
        )
