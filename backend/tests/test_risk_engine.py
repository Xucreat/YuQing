"""Risk Model V2 —— Phase 2-A RiskEngine 单元测试。

覆盖（按实施报告要求）：
  - Severity 计算（仅计真实危害词，语境词不计入）
  - BASE_RISK 底座保留（无危害词也不跌到 0）
  - Event State 单枚举（多状态共存取最缓和）
  - StateFactor 折减（occurred/notice/deploy/prevent/resolved）
  - resolution_flag 由 state=='resolved' 派生
  - 正面情感折减（仅低严重度真实事件生效）
  - Severity Floor（重大事件不因 positive / resolved 降级）
  - 防灾 / 宣教（prevent / notice）降低误报
  - DEFAULT_SEVERITY_KEYWORDS fallback 与注入覆盖

全部为纯函数测试，不连接数据库。
"""
from app.services.risk_engine import (
    BASE_RISK,
    DEFAULT_SEVERITY_KEYWORDS,
    STATE_OCCURRED,
    STATE_NOTICE,
    STATE_PREVENT,
    STATE_RESOLVED,
    RiskEngine,
    RiskRefinement,
)


def _ref(title, content, sentiment):
    return RiskEngine().refine(title, content, sentiment)


# ---------------------------------------------------------------------------
# 1) Severity 只计真实危害词；语境词（投诉/舆情/维权/群体）不计入
# ---------------------------------------------------------------------------
def test_severity_counts_only_real_risk_words():
    # 仅语境词，无真实危害词 → severity=0，但 BASE_RISK 底座保留
    r = _ref("群众投诉维权渠道畅通", "群众反映维权诉求，渠道畅通", "neutral")
    assert r.severity_score == 0
    assert r.final_risk_score == BASE_RISK  # 20，不跌到 0


def test_severity_caps_at_100():
    # 爆炸(90) + 伤亡(90) = 180 → 上限 100
    r = _ref("化工厂爆炸致多人伤亡", "化工厂发生爆炸，造成多人伤亡", "negative")
    assert r.severity_score == 100
    assert r.final_risk_score == 100
    # 无 resolved / prevent 短语（"致"命中 occurred）→ occurred
    assert r.event_state == STATE_OCCURRED
    assert r.resolution_flag is False


# ---------------------------------------------------------------------------
# 2) Event State 单枚举：多状态共存取最缓和（resolved > prevent > deploy > notice > occurred）
# ---------------------------------------------------------------------------
def test_event_state_single_enum_most_mild_wins():
    # 同时含 occurred("致") 与 resolved("解决") → 取 resolved
    r = _ref("化工厂爆炸致多人伤亡，救援已妥善解决", "事故得到解决", "negative")
    assert r.event_state == STATE_RESOLVED
    assert r.resolution_flag is True


def test_event_state_default_occurred_when_no_phrase():
    r = _ref("网络出现一则传言", "某平台出现不实信息", "neutral")
    assert r.event_state == STATE_OCCURRED
    assert r.resolution_flag is False


def test_event_state_notice_lowers_risk():
    # 事故(60)，"通报"命中 notice（因子 0.85）
    r = _ref("政府通报事故调查进展", "相关部门通报事故处理情况", "neutral")
    assert r.event_state == STATE_NOTICE
    # severity_adj = 60*0.85 = 51；floor(≥50)=50；final = max(51,50,20)=51
    assert r.final_risk_score == 51


def test_event_state_prevent_lowers_risk():
    # 事故(60)，"部署/防范/演练"命中 prevent（因子 0.55）
    r = _ref("政府部署防灾演练，防范事故灾害", "开展防灾演练，排查隐患", "neutral")
    assert r.event_state == STATE_PREVENT
    # severity_adj = 60*0.55 = 33；floor(≥50)=50；final = max(33,50,20)=50
    assert r.final_risk_score == 50


# ---------------------------------------------------------------------------
# 3) resolution_flag 由 state=='resolved' 派生
# ---------------------------------------------------------------------------
def test_resolution_flag_derived_from_resolved():
    r = _ref("事故已妥善解决，整改完成", "问题化解，问责到位", "positive")
    assert r.event_state == STATE_RESOLVED
    assert r.resolution_flag is True


def test_resolution_flag_false_when_not_resolved():
    r = _ref("化工厂爆炸致多人伤亡", "现场紧急救援", "negative")
    assert r.event_state != STATE_RESOLVED
    assert r.resolution_flag is False


# ---------------------------------------------------------------------------
# 4) 正面情感折减：仅低严重度真实事件生效；重大事件由 Floor 兜底
# ---------------------------------------------------------------------------
def test_positive_sentiment_reduces_low_severity_event():
    # 谣言(45) + positive → sentiment_adj = min(0.25*(100-45),25)=13.75
    # final = max(45-13.75, 0, 20) = 31
    r = _ref("群众点赞政府辟谣成效显著", "谣言澄清，群众点赞", "positive")
    assert r.severity_score == 45
    assert r.final_risk_score == 31
    assert r.event_state == STATE_OCCURRED


def test_positive_does_not_reduce_baseline_context_only():
    # 仅语境词（投诉/解决），positive → severity=0，final 保持 BASE_RISK(20)
    r = _ref("政府积极回应群众投诉，问题已经解决", "群众投诉得到妥善解决", "positive")
    assert r.severity_score == 0
    assert r.final_risk_score == BASE_RISK  # 20，未被压到更低
    assert r.resolution_flag is True


# ---------------------------------------------------------------------------
# 5) Severity Floor：重大事件不因 positive / resolved 降级
# ---------------------------------------------------------------------------
def test_severity_floor_keeps_major_event_high_when_resolved_and_positive():
    # 爆炸(90)+伤亡(90)=100；state=resolved(因子0.35)→severity_adj=35；
    # positive 且 severity=100 → sentiment_adj=0；floor(≥70)=70
    # final = max(35, 70, 20) = 70（保底，不降级为低危）
    r = _ref(
        "化工厂爆炸致多人伤亡，救援已妥善解决",
        "事故处置圆满，整改完成",
        "positive",
    )
    assert r.severity_score == 100
    assert r.final_risk_score == 70
    assert r.resolution_flag is True


def test_severity_floor_medium_event_not_downgraded_below_50():
    # 事故(60) + resolved + positive → severity_adj=21, sentiment_adj=10
    # floor(≥50)=50 → final = max(11, 50, 20) = 50
    r = _ref("事故已妥善解决，整改完成", "整改完成，群众满意", "positive")
    assert r.severity_score == 60
    assert r.final_risk_score == 50  # 不被压到 low


# ---------------------------------------------------------------------------
# 6) 防灾 / 宣教误报降低（与 occurred 同素材对比）
# ---------------------------------------------------------------------------
def test_prevent_reduces_false_alarm_vs_occurred():
    base = _ref("某工地发生事故造成人员受伤", "工地发生事故", "negative")
    prevent = _ref("政府部署防灾演练，防范事故灾害", "开展演练排查", "neutral")
    assert base.event_state == STATE_OCCURRED
    assert prevent.event_state == STATE_PREVENT
    # 同含「事故」(60)，prevent 因子更低 → 最终分更低
    assert prevent.final_risk_score < base.final_risk_score


# ---------------------------------------------------------------------------
# 7) DEFAULT_SEVERITY_KEYWORDS fallback 与注入覆盖
# ---------------------------------------------------------------------------
def test_default_severity_keywords_fallback_present():
    e = RiskEngine()
    assert "爆炸" in e.severity_keywords
    assert e.severity_keywords["爆炸"] == DEFAULT_SEVERITY_KEYWORDS["爆炸"]
    assert "火灾" in e.severity_keywords


def test_injected_severity_keywords_overrides_default():
    custom = {"火灾": 30}
    e = RiskEngine(severity_keywords=custom)
    assert e.severity_keywords["火灾"] == 30
    # 未指定的真实词仍保留默认
    assert e.severity_keywords["爆炸"] == DEFAULT_SEVERITY_KEYWORDS["爆炸"]


def test_returns_independent_risk_refinement_object():
    r = _ref("化工厂爆炸致多人伤亡", "现场救援", "negative")
    assert isinstance(r, RiskRefinement)
    # RiskRefinement 不污染 AIAnalysisResult（schema 不受影响）
    # Phase 2-A.1：新增 risk_factors 解释字段（仅解释，不参与评分）
    # Phase 2-B.2：新增 risk_category 解释字段（纯标签，不参与评分）
    assert set(r.__dataclass_fields__.keys()) == {
        "severity_score",
        "event_state",
        "resolution_flag",
        "final_risk_score",
        "risk_factors",
        "risk_category",
    }
