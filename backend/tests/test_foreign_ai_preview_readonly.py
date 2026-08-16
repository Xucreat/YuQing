"""Phase 2：外网批量 AI 预览只读化 — 聚焦单元测试（不连接任何数据库）。

仅验证预览路径不调用 AI、不写库（add/flush/commit/delete）、候选按 opinion_id 去重，
以及正式批量运行路径（_run_foreign_ai_batch）未被本阶段改动。

所有用例均使用 MagicMock 模拟 Session，绝不对真实/测试 PostgreSQL 执行任何写入。
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.api import foreign as foreign_api


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _make_rule(rule_type: str, conditions: dict, enabled: bool = True) -> SimpleNamespace:
    return SimpleNamespace(rule_type=rule_type, conditions=conditions, is_enabled=enabled)


def _make_result(risk_score, risk_level="high", risk_category="unknown"):
    return SimpleNamespace(risk_score=risk_score, risk_level=risk_level, risk_category=risk_category)


def _make_db(rules, risk_rows, ai_rows, has_table=True):
    """构造一个只会读、绝不写的 mock Session。

    db.scalars(...) 仅被规则查询使用；db.execute(...) 仅被 AI 结果查询使用；
    inspect(db.get_bind()).has_table(...) 返回 has_table。
    """
    db = MagicMock()
    db.scalars.return_value.all.return_value = list(rules)
    db.execute.return_value.all.return_value = list(ai_rows)
    inspect_mock = MagicMock()
    inspect_mock.return_value.get_bind.return_value.has_table.return_value = has_table
    return db, inspect_mock


def _run_candidate_count(db, opinion_ids, risk_rows, ai_rows, rules, has_table=True):
    db, inspect_mock = _make_db(rules, risk_rows, ai_rows, has_table=has_table)
    # 模拟 DB 查询中的 ForeignAlertRule.is_enabled.is_(True) 过滤（mock 不会执行真正 where）
    enabled_rules = [r for r in rules if getattr(r, "is_enabled", True)]
    db.scalars.return_value.all.return_value = list(enabled_rules)
    with patch("app.api.foreign.inspect", inspect_mock), patch(
        "app.services.foreign_alert_service._current_risk_rows",
        return_value=list(risk_rows),
    ):
        return foreign_api._preview_foreign_candidate_count(db, opinion_ids), db


def _run_event_count(db, opinion_ids, linked_ids, has_table=True):
    db = MagicMock()
    db.scalars.return_value.all.return_value = list(linked_ids)
    inspect_mock = MagicMock()
    inspect_mock.return_value.get_bind.return_value.has_table.return_value = has_table
    with patch("app.api.foreign.inspect", inspect_mock):
        return foreign_api._preview_foreign_event_candidate_count(db, opinion_ids), db


# ---------------------------------------------------------------------------
# _preview_foreign_candidate_count
# ---------------------------------------------------------------------------

def test_candidate_empty_list():
    db, _ = _make_db([], [], [])
    with patch("app.api.foreign.inspect", MagicMock()), patch(
        "app.services.foreign_alert_service._current_risk_rows", return_value=[]
    ):
        assert foreign_api._preview_foreign_candidate_count(db, []) == 0
    db.add.assert_not_called()
    db.flush.assert_not_called()
    db.commit.assert_not_called()


def test_candidate_no_rules():
    val, db = _run_candidate_count(MagicMock(), [1], [], [], rules=[])
    assert val == 0
    db.add.assert_not_called()


def test_candidate_rule_only():
    rule = _make_rule("risk_score", {"threshold": 50})
    result = _make_result(80)
    val, db = _run_candidate_count(MagicMock(), [1], [(result, SimpleNamespace(id=1))], [], rules=[rule])
    assert val == 1  # 命中规则风险的 1 个 opinion


def test_candidate_ai_only():
    rule = _make_rule("ai_risk_score", {"threshold": 60})
    # AI 结果：opinion_id=1, score=70, completed
    val, db = _run_candidate_count(MagicMock(), [1], [], [(1, 70)], rules=[rule])
    assert val == 1


def test_candidate_rule_and_ai_overlap_dedup():
    # 同一 opinion 同时命中规则与 AI → 仅计 1
    rule_score = _make_rule("risk_score", {"threshold": 50})
    rule_ai = _make_rule("ai_risk_score", {"threshold": 60})
    result = _make_result(80)
    val, db = _run_candidate_count(
        MagicMock(), [1], [(result, SimpleNamespace(id=1))], [(1, 70)], rules=[rule_score, rule_ai]
    )
    assert val == 1


def test_candidate_multiple_rules_same_opinion_dedup():
    r1 = _make_rule("risk_score", {"threshold": 50})
    r2 = _make_rule("risk_level", {"levels": ["high"]})
    result = _make_result(80, risk_level="high")
    val, db = _run_candidate_count(
        MagicMock(), [1], [(result, SimpleNamespace(id=1))], [], rules=[r1, r2]
    )
    assert val == 1  # 多条规则命中同一 opinion → 去重为 1


def test_candidate_ai_not_completed_not_counted():
    rule = _make_rule("ai_risk_score", {"threshold": 60})
    # 状态非 completed（这里模拟：cvt 结果未达 completed 过滤）——用分数 None 行模拟未完成
    val, db = _run_candidate_count(MagicMock(), [1], [], [(1, None)], rules=[rule])
    assert val == 0  # 分数空 → 不计数


def test_candidate_null_risk_score_not_counted():
    rule = _make_rule("risk_score", {"threshold": 50})
    result = _make_result(None)  # risk_score=None → _risk_matches 返回 False
    val, db = _run_candidate_count(MagicMock(), [1], [(result, SimpleNamespace(id=1))], [], rules=[rule])
    assert val == 0


def test_candidate_disabled_rule_not_counted():
    rule = _make_rule("risk_score", {"threshold": 50}, enabled=False)
    result = _make_result(80)
    val, db = _run_candidate_count(MagicMock(), [1], [(result, SimpleNamespace(id=1))], [], rules=[rule])
    assert val == 0


def test_candidate_no_write_ever():
    rule = _make_rule("risk_score", {"threshold": 50})
    result = _make_result(80)
    val, db = _run_candidate_count(MagicMock(), [1], [(result, SimpleNamespace(id=1))], [], rules=[rule])
    db.add.assert_not_called()
    db.flush.assert_not_called()
    db.commit.assert_not_called()
    db.delete.assert_not_called()


# ---------------------------------------------------------------------------
# _preview_foreign_event_candidate_count
# ---------------------------------------------------------------------------

def test_event_empty():
    val, db = _run_event_count(MagicMock(), [], [])
    assert val == 0


def test_event_unlinked_counts():
    val, db = _run_event_count(MagicMock(), [1, 2], linked_ids=[])
    assert val == 2


def test_event_linked_not_counted():
    val, db = _run_event_count(MagicMock(), [1, 2], linked_ids=[2])
    assert val == 1  # 仅 1 条未关联事件


def test_event_no_write():
    val, db = _run_event_count(MagicMock(), [1], linked_ids=[])
    db.add.assert_not_called()
    db.flush.assert_not_called()
    db.commit.assert_not_called()


# ---------------------------------------------------------------------------
# _foreign_ai_batch_preview 不调用写入/AI 逻辑
# ---------------------------------------------------------------------------

def _fake_opinion(oid):
    return SimpleNamespace(id=oid, title="t", summary="s", content="c")


def test_preview_does_not_write_or_call_ai():
    fake_rows = [_fake_opinion(1), _fake_opinion(2)]
    event_svc = MagicMock()
    alert_svc = MagicMock()
    ai_svc = MagicMock()
    db = MagicMock()
    # completed_count 查询：db.scalar 返回 0
    db.scalar.return_value = 0
    inspect_mock = MagicMock()
    inspect_mock.return_value.get_bind.return_value.has_table.return_value = True

    payload = SimpleNamespace(
        only_unanalyzed=False,
        force=False,
        token_budget=10_000,
        model_dump=lambda *a, **k: {},
    )
    with patch.object(foreign_api, "_foreign_ai_batch_selection", return_value=fake_rows), patch(
        "app.api.foreign.inspect", inspect_mock
    ), patch("app.api.foreign.resolve_one", return_value={"rule_risk": {"risk_level": "high"}}), patch(
        "app.api.foreign.ForeignEventService", event_svc
    ), patch("app.api.foreign.ForeignAlertService", alert_svc), patch(
        "app.api.foreign.ForeignAIService", ai_svc
    ), patch.object(
        foreign_api, "_preview_foreign_event_candidate_count", return_value=3
    ), patch.object(
        foreign_api, "_preview_foreign_candidate_count", return_value=4
    ):
        result = foreign_api._foreign_ai_batch_preview(db, payload)

    # 统计值来自纯 SELECT 函数
    assert result["possible_event_count"] == 3
    assert result["possible_alert_count"] == 4
    # 关键：预览不得调用 rebuild_candidates / evaluate / AI 服务
    event_svc.return_value.rebuild_candidates.assert_not_called()
    alert_svc.evaluate.assert_not_called()
    ai_svc.return_value.analyze.assert_not_called() if hasattr(ai_svc.return_value, "analyze") else None
    # 预览不得写库
    db.add.assert_not_called()
    db.flush.assert_not_called()
    db.commit.assert_not_called()
    db.delete.assert_not_called()


def test_preview_empty_selection_returns_zero():
    db = MagicMock()
    db.scalar.return_value = 0
    inspect_mock = MagicMock()
    inspect_mock.return_value.get_bind.return_value.has_table.return_value = True
    payload = SimpleNamespace(
        only_unanalyzed=False, force=False, token_budget=10_000, model_dump=lambda *a, **k: {}
    )
    with patch.object(foreign_api, "_foreign_ai_batch_selection", return_value=[]), patch(
        "app.api.foreign.inspect", inspect_mock
    ), patch("app.api.foreign.resolve_one", return_value={}), patch.object(
        foreign_api, "_preview_foreign_event_candidate_count", return_value=0
    ) as ev, patch.object(
        foreign_api, "_preview_foreign_candidate_count", return_value=0
    ) as cnd:
        result = foreign_api._foreign_ai_batch_preview(db, payload)
    assert result["possible_event_count"] == 0
    assert result["possible_alert_count"] == 0
    # 空选择时不应调用两个统计函数（if rows: 守卫）
    ev.assert_not_called()
    cnd.assert_not_called()


def test_preview_exception_falls_back_to_zero():
    """统计异常时回退为 0，接口不抛 500。"""
    fake_rows = [_fake_opinion(1)]
    db = MagicMock()
    db.scalar.return_value = 0
    inspect_mock = MagicMock()
    inspect_mock.return_value.get_bind.return_value.has_table.return_value = True
    payload = SimpleNamespace(
        only_unanalyzed=False, force=False, token_budget=10_000, model_dump=lambda *a, **k: {}
    )
    with patch.object(foreign_api, "_foreign_ai_batch_selection", return_value=fake_rows), patch(
        "app.api.foreign.inspect", inspect_mock
    ), patch("app.api.foreign.resolve_one", return_value={"rule_risk": {"risk_level": "high"}}), patch.object(
        foreign_api, "_preview_foreign_candidate_count", side_effect=RuntimeError("boom")
    ), patch.object(
        foreign_api, "_preview_foreign_event_candidate_count", side_effect=RuntimeError("boom")
    ):
        result = foreign_api._foreign_ai_batch_preview(db, payload)
    assert result["possible_event_count"] == 0
    assert result["possible_alert_count"] == 0


def test_formal_batch_path_unchanged():
    """正式批量运行路径（_run_foreign_ai_batch）仍包含 rebuild_candidates /
    evaluate 写入调用——本阶段未改动它。"""
    import inspect as _inspect

    src = _inspect.getsource(foreign_api._run_foreign_ai_batch)
    assert "rebuild_candidates(" in src
    assert "ForeignAlertService.evaluate(" in src
    assert "db.commit()" in src
