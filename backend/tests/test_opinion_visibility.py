"""Phase Opinion-Visibility-1 测试：展示治理（默认隐藏低价值内容）。

不改数据库结构、不删数据、不改 content_type / admission_reason / decision / risk_score。
仅影响列表查询的展示层过滤。

测试隔离约定：每次运行生成唯一 tag 写入 title，所有列表请求都带 keyword=<tag> 做范围
限定——这样断言不依赖「库里只有本测试数据」，在已有上万条舆情的库上同样成立
（列表 size 上限 100，若用全局计数断言会因分页截断而失败）。
"""
import uuid

import pytest
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.opinion import Opinion

# 本次运行的唯一标记，用于把断言范围限定在本测试创建的数据上。
VIS_TAG = f"vistag{uuid.uuid4().hex[:10]}"

# (content_type, source_type)
SPECS = [
    ("irrelevant", "xhs_note"),
    ("advertising", "xhs_note"),
    ("risk_event", "xhs_note"),
    ("entertainment", "xhs_note"),
    ("news", None),
    (None, None),
]
# 默认列表应可见的条数：6 条中隐藏 irrelevant / advertising 两条。
VISIBLE_COUNT = 4
LOW_VALUE_COUNT = 2


def _make(db: Session, content_type, source_type, region_id):
    op = Opinion(
        title=f"{VIS_TAG}-{content_type}-{uuid.uuid4().hex[:8]}",
        content="content",
        source="XHS" if source_type == "xhs_note" else "测试",
        url=f"https://example.com/vis/{uuid.uuid4().hex}",
        region_id=region_id,
        content_type=content_type,
        source_type=source_type,
        # 历史重算 keep-accepted：低价值内容也保持 decision=accepted
        admission_reason={"decision": "accepted", "note": "historical_recompute_keep_admitted"},
    )
    db.add(op)
    db.commit()
    db.refresh(op)
    return op


@pytest.fixture
def seeded_opinions(seeded_region_id):
    """创建 6 条覆盖各 content_type 的舆情，其中 2 条为低价值（irrelevant/advertising）。"""
    db = SessionLocal()
    created = []
    try:
        for ct, st in SPECS:
            created.append(_make(db, ct, st, seeded_region_id))
        yield created
    finally:
        ids = [op.id for op in created]
        db.close()
        # 用独立会话按 id 批量清理，避免对象过期 / 会话状态影响清理成功率
        cleanup = SessionLocal()
        try:
            if ids:
                cleanup.query(Opinion).filter(Opinion.id.in_(ids)).delete(
                    synchronize_session=False
                )
                cleanup.commit()
        finally:
            cleanup.close()


def _ids(items):
    return {it["id"] for it in items}


def _get(client, auth_headers, **params):
    """带 tag 范围限定的列表请求。"""
    query = {"keyword": VIS_TAG, "size": 100, **params}
    qs = "&".join(f"{k}={v}" for k, v in query.items())
    resp = client.get(f"/api/opinions?{qs}", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_default_list_hides_low_value(seeded_opinions, auth_headers, client):
    """Case 1 + Case 2：默认列表隐藏 irrelevant/advertising，保留 risk_event 等。"""
    body = _get(client, auth_headers)
    items = body["items"]
    ids = _ids(items)

    by_type = {o.content_type: o for o in seeded_opinions}

    # Case 1：低价值默认不返回
    assert by_type["irrelevant"].id not in ids
    assert by_type["advertising"].id not in ids
    # Case 2：业务价值内容仍返回（含 entertainment —— 可能演化为公共事件，不隐藏）
    assert by_type["risk_event"].id in ids
    assert by_type["entertainment"].id in ids
    assert by_type["news"].id in ids
    # content_type 为 NULL 的历史/普通源始终可见
    assert by_type[None].id in ids
    # 返回的条目里不应出现低价值类型
    assert all(it["content_type"] not in ("irrelevant", "advertising") for it in items)
    assert body["total"] == VISIBLE_COUNT


def test_explicit_content_type_overrides_hide(seeded_opinions, auth_headers, client):
    """显式筛选 content_type=irrelevant 时尊重用户意图，返回该类型（即便默认隐藏）。"""
    body = _get(client, auth_headers, content_type="irrelevant")
    ids = _ids(body["items"])
    irrelevant = next(o for o in seeded_opinions if o.content_type == "irrelevant")
    assert irrelevant.id in ids
    assert body["total"] == 1


def test_include_low_value_true_returns_everything(seeded_opinions, auth_headers, client):
    """Case 3：include_low_value=true 返回完整数据（含 irrelevant/advertising）。"""
    body = _get(client, auth_headers, include_low_value="true")
    items = body["items"]
    ids = _ids(items)
    for o in seeded_opinions:
        assert o.id in ids, f"content_type={o.content_type} 未返回"
    assert body["total"] == len(SPECS)
    assert body["total"] == len(items)


def test_historical_xhs_low_value_not_deleted(seeded_opinions, auth_headers, client):
    """Case 4：历史 xhs_note + irrelevant + accepted 数据不被删除，仅默认隐藏。"""
    irrelevant = next(
        o for o in seeded_opinions
        if o.content_type == "irrelevant" and o.source_type == "xhs_note"
    )
    # 默认列表不出现
    assert irrelevant.id not in _ids(_get(client, auth_headers)["items"])

    # 数据库中仍存在（未删除）
    db = SessionLocal()
    try:
        row = db.get(Opinion, irrelevant.id)
        assert row is not None, "历史低价值数据被删除——违反本阶段约束"
        # 准入结果未被本阶段改动
        assert row.content_type == "irrelevant"
        assert row.source_type == "xhs_note"
        assert row.admission_reason["decision"] == "accepted"
    finally:
        db.close()

    # include_low_value 可查回，且详情接口始终可访问（展示过滤只作用于列表）
    inc = _get(client, auth_headers, include_low_value="true")
    assert irrelevant.id in _ids(inc["items"])
    detail = client.get(f"/api/opinions/{irrelevant.id}", headers=auth_headers)
    assert detail.status_code == 200
    assert detail.json()["content_type"] == "irrelevant"


def test_pagination_total_consistent(seeded_opinions, auth_headers, client):
    """Case 5：total 与实际可翻页条目一致，避免前端分页显示错误。"""
    default = _get(client, auth_headers)
    assert default["total"] == VISIBLE_COUNT == len(default["items"])

    full = _get(client, auth_headers, include_low_value="true")
    assert full["total"] == len(SPECS) == len(full["items"])
    # 全量比默认多出的正是 2 条低价值（irrelevant + advertising）
    assert full["total"] - default["total"] == LOW_VALUE_COUNT

    # 真分页：total 不变，逐页取回的条目集合恰好等于单页结果（无重复 / 无丢失）
    page1 = _get(client, auth_headers, page=1, size=3)
    page2 = _get(client, auth_headers, page=2, size=3)
    assert page1["total"] == page2["total"] == VISIBLE_COUNT
    assert len(page1["items"]) == 3
    assert len(page2["items"]) == VISIBLE_COUNT - 3
    assert _ids(page1["items"]) | _ids(page2["items"]) == _ids(default["items"])
