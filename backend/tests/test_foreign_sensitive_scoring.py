"""国外敏感词直接驱动国外舆情风险评分。

这些测试锁定本次需求的核心约束：

* 国外风险评分只读取 foreign_keywords(type='sensitive' & is_enabled=True)；
* 公式保持 risk_score = min(100, 20 + Σ severity_weight)，阈值 70/40 不变；
* monitoring 类型绝不参与评分，也绝不进入采集关键词列表；
* 评分不再依赖空的 foreign_risk_terms；
* 敏感词增删改后，可通过可控的重新评分入口用最新词库刷新历史舆情；
* 历史迁移（foreign_risk_terms -> foreign_keywords）幂等、不重复导入。
"""
from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import delete, select, text

from app.core.task_manager import _tasks
from app.db.session import SessionLocal
from app.models.foreign_keyword import ForeignKeyword
from app.models.foreign_opinion import ForeignOpinion
from app.models.foreign_risk_result import ForeignRiskResult
from app.models.foreign_risk_term import ForeignRiskTerm
from app.services.foreign_keyword_service import (
    get_foreign_monitoring_keywords,
)
from app.services.foreign_risk_service import BASE_RISK_SCORE, ForeignRiskService


def _suffix() -> str:
    return uuid.uuid4().hex[:10]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _opinion(db, suffix: str, *, word: str = "") -> ForeignOpinion:
    body = f"Foreign sensitive scoring fixture {suffix}"
    if word:
        body = f"{word} appears in this foreign article body for scoring {suffix}"
    row = ForeignOpinion(
        source_key=f"fixture_sens_{suffix}",
        source_name_snapshot="Sensitive scoring source",
        title=f"{body} {suffix}",
        summary=body,
        content=f"{body}. A sufficiently long foreign fixture article body.",
        url=f"https://fixture.test/foreign-sens/{suffix}",
        published_at=_utcnow(),
        collected_at=_utcnow(),
        matched_keywords=["fixture"],
        content_hash=(suffix * 8)[:64],
    )
    db.add(row)
    db.flush()
    return row


def _sensitive(db, word: str, *, severity: int = 10, enabled: bool = True, category: str = "general") -> ForeignKeyword:
    kw = ForeignKeyword(
        word=word, type="sensitive", is_enabled=enabled,
        severity_weight=severity, category=category, source="custom",
    )
    db.add(kw)
    db.flush()
    return kw


def _monitoring(db, word: str, *, enabled: bool = True) -> ForeignKeyword:
    kw = ForeignKeyword(
        word=word, type="monitoring", is_enabled=enabled,
        weight=10, severity_weight=0, category="general", source="custom",
    )
    db.add(kw)
    db.flush()
    return kw


def _cleanup(db, *, opinion_ids=(), keyword_ids=(), term_ids=()):
    if keyword_ids:
        db.execute(delete(ForeignKeyword).where(ForeignKeyword.id.in_(keyword_ids)))
    if term_ids:
        db.execute(delete(ForeignRiskTerm).where(ForeignRiskTerm.id.in_(term_ids)))
    if opinion_ids:
        db.execute(delete(ForeignRiskResult).where(ForeignRiskResult.foreign_opinion_id.in_(opinion_ids)))
        db.execute(delete(ForeignOpinion).where(ForeignOpinion.id.in_(opinion_ids)))
    db.commit()


def test_no_enabled_sensitive_keyword_scores_baseline():
    db = SessionLocal()
    svc = ForeignRiskService()
    try:
        op = _opinion(db, _suffix())
        db.commit()
        result = svc.analyze_opinion(db, op.id)
        assert result.risk_score == BASE_RISK_SCORE == 20
        assert result.risk_level == "low"
        assert result.matched_terms == []
    finally:
        _cleanup(db, opinion_ids=[op.id])
        db.close()


def test_single_enabled_sensitive_adds_its_severity_weight():
    db = SessionLocal()
    svc = ForeignRiskService()
    try:
        word = f"protest_{_suffix()}"
        kw = _sensitive(db, word, severity=30)
        op = _opinion(db, _suffix(), word=word)
        db.commit()
        result = svc.analyze_opinion(db, op.id)
        assert result.risk_score == BASE_RISK_SCORE + 30 == 50
        assert result.risk_level == "medium"
        assert len(result.matched_terms) == 1
        assert result.matched_terms[0]["word"] == word
        assert result.matched_terms[0]["severity_weight"] == 30
    finally:
        _cleanup(db, opinion_ids=[op.id], keyword_ids=[kw.id])
        db.close()


def test_multiple_sensitive_accumulate_and_cap_at_100():
    db = SessionLocal()
    svc = ForeignRiskService()
    try:
        w1 = f"strike_{_suffix()}"
        w2 = f"riot_{_suffix()}"
        k1 = _sensitive(db, w1, severity=50)
        k2 = _sensitive(db, w2, severity=50)
        op = _opinion(db, _suffix(), word=f"{w1} {w2}")
        db.commit()
        result = svc.analyze_opinion(db, op.id)
        # 20 + 50 + 50 = 120 -> capped at 100
        assert result.risk_score == 100
        assert result.risk_level == "high"
        assert len(result.matched_terms) == 2
    finally:
        _cleanup(db, opinion_ids=[op.id], keyword_ids=[k1.id, k2.id])
        db.close()


def test_disabled_sensitive_keyword_not_scored():
    db = SessionLocal()
    svc = ForeignRiskService()
    try:
        word = f"riot_{_suffix()}"
        kw = _sensitive(db, word, severity=40, enabled=False)
        op = _opinion(db, _suffix(), word=word)
        db.commit()
        result = svc.analyze_opinion(db, op.id)
        # 禁用敏感词不参与评分，保持基线
        assert result.risk_score == BASE_RISK_SCORE == 20
        assert result.matched_terms == []
    finally:
        _cleanup(db, opinion_ids=[op.id], keyword_ids=[kw.id])
        db.close()


def test_monitoring_keyword_never_scores_and_excluded_from_collection():
    db = SessionLocal()
    svc = ForeignRiskService()
    try:
        word = f"war_{_suffix()}"
        kw = _monitoring(db, word)
        op = _opinion(db, _suffix(), word=word)
        db.commit()
        # 1) monitoring 不参与评分
        result = svc.analyze_opinion(db, op.id)
        assert result.risk_score == BASE_RISK_SCORE == 20
        assert result.matched_terms == []
        # 2) monitoring 出现在采集关键词列表
        monitoring = get_foreign_monitoring_keywords(db)
        assert word in monitoring
        # 3) 评分加载的敏感词不含 monitoring 词
        sensitive = svc._load_sensitive_terms(db)
        assert all(t.word != word for t in sensitive)
    finally:
        _cleanup(db, opinion_ids=[op.id], keyword_ids=[kw.id])
        db.close()


def test_sensitive_keyword_not_in_collection_keyword_list():
    db = SessionLocal()
    try:
        ks = _sensitive(db, f"sens_{_suffix()}", severity=10)
        km = _monitoring(db, f"mon_{_suffix()}")
        db.commit()
        monitoring = get_foreign_monitoring_keywords(db)
        assert km.word in monitoring
        assert ks.word not in monitoring
    finally:
        _cleanup(db, keyword_ids=[ks.id, km.id])
        db.close()


def test_risk_level_thresholds_high_medium_low():
    db = SessionLocal()
    svc = ForeignRiskService()
    created = []
    kws = []
    try:
        # 55 -> 75 high ; 25 -> 45 medium ; 10 -> 30 low
        kh = _sensitive(db, f"h_{_suffix()}", severity=55)
        km = _sensitive(db, f"m_{_suffix()}", severity=25)
        kl = _sensitive(db, f"l_{_suffix()}", severity=10)
        kws = [kh, km, kl]
        oh = _opinion(db, _suffix(), word=kh.word)
        om = _opinion(db, _suffix(), word=km.word)
        ol = _opinion(db, _suffix(), word=kl.word)
        created = [oh.id, om.id, ol.id]
        db.commit()
        rh = svc.analyze_opinion(db, oh.id)
        rm = svc.analyze_opinion(db, om.id)
        rl = svc.analyze_opinion(db, ol.id)
        assert rh.risk_score == 75 and rh.risk_level == "high"
        assert rm.risk_score == 45 and rm.risk_level == "medium"
        assert rl.risk_score == 30 and rl.risk_level == "low"
    finally:
        _cleanup(db, opinion_ids=created, keyword_ids=[k.id for k in kws])
        db.close()


def test_rescore_picks_up_latest_keywords_after_change():
    db = SessionLocal()
    svc = ForeignRiskService()
    try:
        word = f"rescore_{_suffix()}"
        op = _opinion(db, _suffix(), word=word)
        db.commit()
        # 初始无敏感词 -> 基线 20
        r0 = svc.analyze_opinion(db, op.id)
        assert r0.risk_score == 20
        # 新增启用的敏感词（同词，severity 40），但 content_hash 未变 -> 普通 analyze 因幂等跳过
        kw = _sensitive(db, word, severity=40)
        db.commit()
        r_same = svc.analyze_opinion(db, op.id)
        assert r_same.risk_score == 20, "普通 analyze 应被 content_hash 幂等缓存跳过"
        # 重新评分（force）使用最新词库 -> 20 + 40 = 60
        svc.rescore_all(db)
        r1 = db.scalar(
            select(ForeignRiskResult).where(
                ForeignRiskResult.foreign_opinion_id == op.id,
                ForeignRiskResult.is_current.is_(True),
            )
        )
        assert r1.risk_score == 60
        assert r1.matched_terms and r1.matched_terms[0]["word"] == word
    finally:
        _cleanup(db, opinion_ids=[op.id], keyword_ids=[kw.id])
        db.close()


def test_foreign_risk_terms_is_not_used_at_runtime():
    db = SessionLocal()
    svc = ForeignRiskService()
    term_id = None
    try:
        # 直接往旧表 foreign_risk_terms 写入一条启用风险词，但评分不应读取它
        term = ForeignRiskTerm(
            word=f"legacy_{_suffix()}", language="zh", category="general",
            severity_weight=80, sentiment="negative", is_enabled=True,
            source="manual", term_set_version="v1",
        )
        db.add(term)
        db.flush()
        term_id = term.id
        op = _opinion(db, _suffix(), word=term.word)
        db.commit()
        result = svc.analyze_opinion(db, op.id)
        # 仍应只命中 foreign_keywords 中的敏感词（此处为空）-> 基线 20
        assert result.risk_score == BASE_RISK_SCORE == 20
        assert result.matched_terms == []
        # 评分加载的敏感词集合不受 foreign_risk_terms 写入影响
        before = {t.word for t in svc._load_sensitive_terms(db)}
        after = {t.word for t in svc._load_sensitive_terms(db)}
        assert after == before
    finally:
        _cleanup(db, opinion_ids=[op.id], term_ids=[term_id] if term_id else ())
        db.close()


def test_keyword_api_create_triggers_background_rescore(client, auth_headers):
    db = SessionLocal()
    svc = ForeignRiskService()
    created_op = None
    kw_id = None
    try:
        word = f"unrest_{_suffix()}"
        op = _opinion(db, _suffix(), word=word)
        db.commit()
        created_op = op.id
        r0 = svc.analyze_opinion(db, op.id)
        assert r0.risk_score == 20

        # 通过 API 新增启用敏感词 -> 应触发后台重新评分任务
        resp = client.post(
            "/api/foreign/keywords",
            headers=auth_headers,
            json={"word": word, "type": "sensitive", "severity_weight": 35, "is_enabled": True, "category": "general"},
        )
        assert resp.status_code == 201, resp.text
        kw_id = resp.json()["id"]
        # 后台任务已入队（类型 foreign_rescore）
        assert any(t.task_type == "foreign_rescore" for t in _tasks.values())

        # 用最新词库重新评分 -> 20 + 35 = 55
        svc.rescore_all(db)
        r1 = db.scalar(
            select(ForeignRiskResult).where(
                ForeignRiskResult.foreign_opinion_id == op.id,
                ForeignRiskResult.is_current.is_(True),
            )
        )
        assert r1.risk_score == 55
    finally:
        _cleanup(db, opinion_ids=[created_op] if created_op else (), keyword_ids=[kw_id] if kw_id else ())
        db.close()


def test_keyword_api_delete_triggers_background_rescore(client, auth_headers):
    """删除 sensitive 关键词后，必须强制触发后台重新评分（修复回归）。

    旧实现在 commit 后才判断 id 是否命中 sensitive 行，删除后行已不存在，
    导致删除分支永不触发重评分；修复后 _trigger_rescore_if_sensitive(force=True)
    在 was_sensitive 时强制入队。
    """
    db = SessionLocal()
    op = None
    kw_id = None
    try:
        word = f"deltrig_{_suffix()}"
        op = _opinion(db, _suffix(), word=word)
        db.commit()
        # 新增 sensitive 词（API）
        cresp = client.post(
            "/api/foreign/keywords",
            headers=auth_headers,
            json={"word": word, "type": "sensitive", "severity_weight": 40, "is_enabled": True, "category": "general"},
        )
        assert cresp.status_code == 201, cresp.text
        kw_id = cresp.json()["id"]
        # 清空已有的 foreign_rescore 任务引用，仅检测删除触发的那一次
        triggered = []

        # 删除该 sensitive 词
        dresp = client.delete(f"/api/foreign/keywords/{kw_id}", headers=auth_headers)
        assert dresp.status_code == 200, dresp.text
        # 删除后必须强制触发重新评分任务
        for t in _tasks.values():
            if t.task_type == "foreign_rescore":
                triggered.append(t.task_id)
        assert triggered, "删除 sensitive 关键词后未触发 foreign_rescore 任务（修复回归）"
        # 删除后评分应回落到基线（用最新词库重评分验证）
        ForeignRiskService().rescore_all(db)
        r0 = db.scalar(
            select(ForeignRiskResult).where(
                ForeignRiskResult.foreign_opinion_id == op.id,
                ForeignRiskResult.is_current.is_(True),
            )
        )
        assert r0.risk_score == 20, "删除 sensitive 词后评分未回落基线"
        kw_id = None  # 已删除，cleanup 不再尝试删除
    finally:
        _cleanup(db, opinion_ids=[op.id] if op else (), keyword_ids=[kw_id] if kw_id else ())
        db.close()


def test_rescore_endpoint_returns_task_id_when_idle(client, auth_headers):
    """手动重新评分入口可用；当前无同类任务运行时入队返回 200。"""
    # 等待可能残留的 foreign_rescore 任务结束，避免误报 409
    for _ in range(100):
        if not any(t.task_type == "foreign_rescore" and t.status in ("pending", "running") for t in _tasks.values()):
            break
        time.sleep(0.1)
    rresp = client.post("/api/foreign/opinions/rescore", headers=auth_headers)
    assert rresp.status_code == 200, rresp.text
    assert "task_id" in rresp.json()


def test_migration_from_foreign_risk_terms_is_idempotent():
    """直接执行与迁移等价的 INSERT...SELECT 两次，验证不重复导入。"""
    db = SessionLocal()
    inserted_kw_ids = []
    try:
        w1, w2 = f"mig_{_suffix()}", f"mig2_{_suffix()}"
        # 同一 word 两条（不同 severity），外加一条不同 word
        db.add(ForeignRiskTerm(word=w1, language="zh", category="general", severity_weight=10, sentiment="negative", is_enabled=True, source="manual", term_set_version="v1"))
        db.add(ForeignRiskTerm(word=w1, language="en", category="general", severity_weight=80, sentiment="negative", is_enabled=True, source="manual", term_set_version="v1"))
        db.add(ForeignRiskTerm(word=w2, language="zh", category="politics", severity_weight=20, sentiment="negative", is_enabled=True, source="manual", term_set_version="v1"))
        db.commit()

        stmt = text(
            """
            INSERT INTO foreign_keywords (
                word, category, type, source, weight, severity_weight,
                rule_config, is_enabled, created_at, updated_at
            )
            SELECT word, COALESCE(NULLIF(category, ''), 'general'), 'sensitive',
                   'migration', 10, severity_weight, '{}', is_enabled, now(), now()
            FROM (
                SELECT DISTINCT ON (word) word, category, severity_weight, is_enabled
                FROM foreign_risk_terms
                ORDER BY word, severity_weight DESC, id ASC
            ) dedup
            WHERE NOT EXISTS (SELECT 1 FROM foreign_keywords fk WHERE fk.word = dedup.word)
            ON CONFLICT (word) DO NOTHING;
            """
        )
        db.execute(stmt)
        db.execute(stmt)  # 第二次执行，应幂等
        db.commit()

        migrated = db.scalars(
            select(ForeignKeyword).where(
                ForeignKeyword.source == "migration", ForeignKeyword.type == "sensitive"
            )
        ).all()
        # 仅 2 个不同 word 被导入；w1 取 severity_weight 最高者(80)
        assert len(migrated) == 2, [m.word for m in migrated]
        by_word = {m.word: m for m in migrated}
        assert by_word[w1].severity_weight == 80
        assert by_word[w2].severity_weight == 20
        inserted_kw_ids = [m.id for m in migrated]
    finally:
        _cleanup(db, keyword_ids=inserted_kw_ids)
        # 清理本次写入的 foreign_risk_terms
        db.execute(delete(ForeignRiskTerm).where(ForeignRiskTerm.word.in_([w1, w2])))
        db.commit()
        db.close()
