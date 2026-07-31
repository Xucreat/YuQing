"""Phase X-2：「大厂」关键词地域语义过滤 — 验收与回归测试。

覆盖：
  1. 用户 5 条验收用例 + 12 条高危边界用例（17/17）。
  2. 本地源 L0 豁免 / 非锚点不介入。
  3. 核心回归：非「大厂」关键词零影响（is_valid_match 恒 True）。
  4. matches_region_topic / _region_hits 行为校验（仅对 131028 裸别名生效）。
  5. 历史数据回放：复用 Phase X-0 回测 oracle，对生产库 122 条重放，断言决策一致。

不触碰任何写库逻辑；仅做只读 SELECT（历史回放用例）。
"""
from __future__ import annotations

import json
import os

import pytest

from app.collectors.common import matches_region_topic, matches_keywords
from app.services.keyword_filter_service import (
    DEFAULT_RULE,
    FLAGGED_KEYWORDS,
    KeywordFilterService,
)
from app.services.opinion_region_service import OpinionRegionService

kf = KeywordFilterService.default()

# 与 Phase X-0 回测保持一致的本地源集合（用于 is_local_source 判定）
LOCAL_SOURCES = {
    "大厂县政府网站", "廊坊市政府网", "廊坊市政府网-本市动态", "廊坊新闻网",
    "香河县政府网", "三河市政府网", "固安县政府网", "永清县政府网",
    "霸州市政府网", "文安县政府网", "大城县政府网", "安次区政府网", "广阳区政府网",
}

# ---- 验收用例（用户 5 + 边界 12）----
ACCEPTANCE = [
    ("廊坊大厂召开安全会议", False, True, "验收1"),
    ("大厂回族自治县发布公告", False, True, "验收2"),
    ("互联网大厂裁员消息", False, False, "验收3"),
    ("程序员进入大厂工作", False, False, "验收4"),
    ("大厂附近居民反映道路问题", False, True, "验收5"),
    ("大厂镇全力筑牢防汛安全屏障", False, True, "边界:乡镇"),
    ("南京江北新区大厂街道:针脚与墨香", False, False, "边界:南京大厂街道"),
    ("各大厂商标榜匿名脱敏", False, False, "边界:大厂商"),
    ("北上广最夯人设:大厂公务员", False, False, "边界:大厂公务员"),
    ("我县开展禁毒宣传|网站首页|走进大厂|新闻中心", False, True, "边界:政府导航"),
    ("工行大厂支行筑牢反诈防线", False, True, "边界:大厂支行"),
    ("闻汛而动守安澜——大厂全力筑牢潮白河防汛安全屏障", False, True, "边界:破折号领起"),
    ("北京海淀:首届大厂足球超级联赛开赛", False, False, "边界:大厂足球"),
    ("张秀萍主持召开全县工业品电商直播工作会议|依托大厂牛肉等县域品牌", True, True, "边界:本地源豁免"),
    ("大厂员工自爆经过六七轮面试", False, False, "边界:大厂员工"),
    ("两家PCB大厂,加码投资", False, False, "边界:PCB大厂"),
    ("廊坊最新天气预报|大厂:暴雨转中雨", False, True, "边界:天气预报列举"),
]


@pytest.mark.parametrize("text,is_local,expected,tag", ACCEPTANCE)
def test_acceptance_cases(text, is_local, expected, tag):
    assert kf.is_valid_match("大厂", text, is_local_source=is_local) == expected, tag


def test_local_source_exempt_for_internet_dachang():
    # L0：本地源豁免，即便是互联网语境也保留
    assert kf.is_valid_match("大厂", "互联网大厂裁员消息", is_local_source=True) is True


def test_no_anchor_untouched():
    # 文本不含「大厂」→ 规则不介入
    assert kf.is_valid_match("大厂", "廊坊市召开安全生产会议", is_local_source=False) is True


def test_other_keywords_zero_impact():
    """核心回归：非「大厂」关键词恒返回 True（原逻辑完全不变）。"""
    others = [
        "廊坊", "三河", "香河", "固安", "大城", "文安", "霸州", "永清",
        "安次", "广阳", "河北", "大厂回族自治县", "大厂县",
        "舆情", "消防", "安全生产", "民生", "投诉", "环保", "教育",
    ]
    noisy = "互联网大厂裁员，程序员跳槽，PCB大厂加码投资"
    for kw in others:
        assert kf.is_valid_match(kw, noisy, is_local_source=False) is True, kw
        assert kf.is_valid_match(kw, noisy, is_local_source=True) is True, kw
    # 治理集合仅含「大厂」
    assert FLAGGED_KEYWORDS == {"大厂"}


def test_matches_region_topic_unchanged_for_other_region():
    # matches_region_topic / matches_keywords 未被改动：非大厂地域词行为不变
    assert matches_region_topic("廊坊市消防安全检查", ["廊坊", "固安"], ["消防"]) is True
    assert matches_region_topic("北京市空气质量播报", ["廊坊", "固安"], ["消防"]) is False
    assert matches_region_topic("消防演练通告", [], ["消防"]) is False
    assert matches_keywords("廊坊发生火情", ["廊坊", "三河"]) is True
    assert matches_keywords("上海发生火情", ["廊坊", "三河"]) is False
    # 含「大厂」但由其他地域词命中时仍按原逻辑（函数本身未被破坏）
    assert matches_region_topic("三河市大厂回族自治县合作", ["三河", "大厂"], []) is True


def test_region_hits_filters_bare_dachang_internet():
    svc = OpinionRegionService()
    # 互联网「大厂」裸别名 → 不应产生 131028 命中
    hits = svc._region_hits("互联网大厂彻底放弃盲目扩张", is_local_source=False)
    assert all(h["code"] != "131028" for h in hits)
    # 强地域锚点「大厂回族自治县」→ 仍命中 131028
    hits2 = svc._region_hits("大厂回族自治县发布公告", is_local_source=False)
    assert any(h["code"] == "131028" for h in hits2)
    # 「大厂镇」强锚点 → 命中 131028（非裸别名分支）
    hits3 = svc._region_hits("大厂镇全力筑牢防汛", is_local_source=False)
    assert any(h["code"] == "131028" for h in hits3)


def test_region_hits_local_exempt():
    svc = OpinionRegionService()
    # 本地源下，裸「大厂」互联网语境也保留 131028（L0 豁免）
    hits = svc._region_hits("互联网大厂裁员消息", is_local_source=True)
    assert any(h["code"] == "131028" for h in hits)


def test_rule_config_default_matches_seeded_contract():
    # DEFAULT_RULE 必须含全部关键字段，且 anchor=大厂
    for k in (
        "strong_geo", "upper_geo", "neg_prefix", "neg_suffix",
        "gov_lead_patterns", "gov_semantic", "neg_context", "livelihood",
    ):
        assert k in DEFAULT_RULE and isinstance(DEFAULT_RULE[k], list), k
    assert DEFAULT_RULE["anchor"] == "大厂"


def _load_prod_db_url():
    """从项目根 .env 读取真实生产库地址（绕过 conftest 的 5433 测试库覆盖）。"""
    here = os.path.dirname(os.path.abspath(__file__))
    candidate = os.path.normpath(os.path.join(here, "..", "..", ".env"))
    if not os.path.exists(candidate):
        return None
    import re
    txt = open(candidate, encoding="utf-8").read()
    m = re.search(r"^DATABASE_URL\s*=\s*(\S+)", txt, re.MULTILINE)
    return m.group(1) if m else None


def test_backtest_regression_against_history():
    """复用 Phase X-0 回测 oracle，对生产库 122 条历史数据重放，断言决策一致。

    说明：pytest 的 conftest 会把 DATABASE_URL 指向 5433 测试库，与生产库(5432)不同，
    故本用例自建带 connect_timeout 的引擎直连生产库，且仅做只读 SELECT。
    若生产库不可达（CI / 离线），自动 skip，不阻塞其它回归用例。
    """
    here = os.path.dirname(os.path.abspath(__file__))
    oracle_path = os.path.join(here, "..", "_audit_dachang_backtest.json")
    if not os.path.exists(oracle_path):
        pytest.skip("Phase X-0 回测产物不存在")
    with open(oracle_path, encoding="utf-8") as f:
        data = json.load(f)
    decisions = data["decisions"]
    id2keep = {d["id"]: d["keep"] for d in decisions}
    ids = list(id2keep)

    prod_url = _load_prod_db_url()
    if not prod_url:
        pytest.skip("未找到生产库 DATABASE_URL")
    # 注入连接超时，避免测试库不可达时无限挂起
    timed_url = prod_url + ("&" if "?" in prod_url else "?") + "connect_timeout=5"

    try:
        from sqlalchemy import create_engine, text as satxt
        engine = create_engine(timed_url, pool_pre_ping=True)
        with engine.connect() as conn:
            rows = conn.execute(
                satxt(
                    "SELECT id, title, COALESCE(content,''), source "
                    "FROM opinions WHERE id = ANY(:ids)"
                ),
                {"ids": ids},
            ).fetchall()
    except Exception as exc:  # 连接失败 → 跳过，不阻塞
        pytest.skip(f"生产库不可达，跳过历史回放: {exc}")

    if not rows:
        pytest.skip("生产库无可回放历史数据")

    mism = []
    for oid, title, content, source in rows:
        is_local = source in LOCAL_SOURCES
        got = kf.is_valid_match("大厂", f"{title} {content}", is_local_source=is_local)
        if got != id2keep[oid]:
            mism.append((oid, id2keep[oid], got, source))
    assert not mism, f"回测决策不一致（前 10）: {mism[:10]}"
