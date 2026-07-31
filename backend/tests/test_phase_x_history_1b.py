"""Phase X-History-1B 统计口径收口验收。

本文件只验证「统计口径收口」是否正确，不修改任何数据：
- A 类（生产库只读验收，RUN_PHASE1B_PROD=1 时运行）：直接连接生产库(127.0.0.1:5432)，
  断言 Dashboard / Report / 地域下钻 / Event 统计在 geo_filtered 与 deprecated 口径下的
  去噪逻辑正确。全部为 SELECT，零写入。
  说明：生产库持续采集，总数会随时间漂移（审计基线 total=859 / 廊坊市=689，运行期已因
  新增真实廊坊舆情变为 861 / 691）。因此本测试断言「排除量」不变量而非绝对数：
    - 总览排除的污染数 == 73（geo_filtered 标记数）
    - 事件排除的废弃数 == 12（deprecated 数）
    - 大厂区排除数 == 22，廊坊市排除数 == 51（Phase X-History-1A 标记结果）
  这才是收口正确性的严谨证明。
- B 类（events deprecated 状态支持，默认连接测试库 127.0.0.1:5433）：
  契约校验 + 行为校验（可筛选 deprecated；deprecated -> active 恢复不产生 500）。
  测试库会话显式绑定 127.0.0.1，避免 localhost 在 psycopg 下优先解析 IPv6(::1) 挂起。
"""

import os
from pathlib import Path
from typing import get_args

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.core.cache import cache_clear
from app.services import dashboard_service, report_service
from app.api import events as events_api
from app.schemas.event import EventStatus

# 生产库只读验收开关（默认关闭，避免污染常规 CI / 测试库运行）
RUN_PROD = os.environ.get("RUN_PHASE1B_PROD") == "1"


def _prod_engine():
    """从仓库根 .env 读取生产库 URL（绕过 conftest 对测试库 5433 的覆盖）。"""
    env_path = Path(__file__).resolve().parents[2] / ".env"
    if not env_path.exists():
        return None
    for line in env_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("DATABASE_URL="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    return None


@pytest.fixture(scope="module")
def prod_engine():
    if not RUN_PROD:
        pytest.skip("RUN_PHASE1B_PROD != 1：跳过生产库只读验收")
    url = _prod_engine()
    if not url:
        pytest.skip("无法解析生产库 DATABASE_URL")
    # 127.0.0.1 直连，规避 localhost 在 psycopg 下的 IPv6 解析挂起
    if "localhost" in url:
        url = url.replace("localhost", "127.0.0.1")
    eng = create_engine(url, pool_pre_ping=True, connect_args={"connect_timeout": 5})
    # 身份门禁：确认连接到正确的生产库且迁移头一致
    try:
        with eng.connect() as c:
            ver = c.execute(text("select version_num from alembic_version")).scalar()
            db = c.execute(text("select current_database()")).scalar()
        # Phase X-History-1A/1B 治理迁移头（geo_filtered + deprecated 支持）
        assert ver in (
            "p29_history_geo_filtered",
            "p30_event_actions_deprecated",
        ), f"alembic head 不符: {ver}"
        assert db == "opinion_db", f"数据库不符: {db}"
    except Exception as ex:  # noqa: BLE001
        pytest.skip(f"生产库不可达或身份不符: {ex}")
    return eng


# ------------------------- A. 生产库只读验收 -------------------------
def test_dashboard_stats_dedup(prod_engine) -> None:
    cache_clear()
    with Session(prod_engine) as db:
        stats = dashboard_service.get_dashboard_stats(db, days=9999)
        total_all = db.execute(text("select count(*) from opinions")).scalar()
        gf = db.execute(
            text("select count(*) from opinions where geo_filtered=true")
        ).scalar()
        total_events = db.execute(text("select count(*) from events")).scalar()
        deprecated = db.execute(
            text("select count(*) from events where status='deprecated'")
        ).scalar()
        hr = db.execute(
            text(
                "select count(*) from opinions "
                "where risk_score >= 70 and geo_filtered is not true"
            )
        ).scalar()
    # 标记数量不变量（数据治理结果必须保持不动）
    assert gf == 73, gf
    assert deprecated == 12, deprecated
    # 去噪口径不变量：总览排除 73 条污染、事件排除 12 条废弃
    assert stats["total"] == total_all - gf, (stats["total"], total_all, gf)
    assert stats["event_count"] == total_events - deprecated
    assert stats["high_risk"] == hr


def test_region_children_dedup(prod_engine) -> None:
    cache_clear()
    with Session(prod_engine) as db:
        res = dashboard_service.get_region_children(db, "河北省", days=9999)
        r1_all = db.execute(
            text("select count(*) from opinions where region_id=1")
        ).scalar()
        r1_gf = db.execute(
            text("select count(*) from opinions where region_id=1 and geo_filtered=true")
        ).scalar()
        r12_all = db.execute(
            text("select count(*) from opinions where region_id=12")
        ).scalar()
        r12_gf = db.execute(
            text("select count(*) from opinions where region_id=12 and geo_filtered=true")
        ).scalar()
    assert res is not None, "未找到河北省下钻数据"
    by_name = {r["region_name"]: r["count"] for r in res["raw"]}
    # 地域下钻同样排除 geo_filtered：大厂/廊坊净计数 = 全量 - 标记数
    assert by_name.get("大厂回族自治县") == r1_all - r1_gf, by_name
    assert by_name.get("廊坊市") == r12_all - r12_gf, by_name
    # 已知标记结果（Phase X-History-1A）：大厂 22 条、廊坊 51 条污染被排除
    assert r1_gf == 22, r1_gf
    assert r12_gf == 51, r12_gf


def test_report_overview_matches_dashboard(prod_engine) -> None:
    cache_clear()
    with Session(prod_engine) as db:
        ov = report_service.build_overview(db, days=9999)
        total_all = db.execute(text("select count(*) from opinions")).scalar()
        gf = db.execute(
            text("select count(*) from opinions where geo_filtered=true")
        ).scalar()
        total_events = db.execute(text("select count(*) from events")).scalar()
        deprecated = db.execute(
            text("select count(*) from events where status='deprecated'")
        ).scalar()
    # 报告导出与 Dashboard 同一去噪口径
    assert ov["total"] == total_all - gf, (ov["total"], total_all, gf)
    assert ov["event_count"] == total_events - deprecated


def test_geo_filtered_and_deprecated_counts(prod_engine) -> None:
    with Session(prod_engine) as db:
        gf = db.execute(
            text("select count(*) from opinions where geo_filtered=true")
        ).scalar()
        deprecated = db.execute(
            text("select count(*) from events where status='deprecated'")
        ).scalar()
        r1 = db.execute(
            text(
                "select count(*) from opinions "
                "where region_id=1 and geo_filtered is not true"
            )
        ).scalar()
        r12 = db.execute(
            text(
                "select count(*) from opinions "
                "where region_id=12 and geo_filtered is not true"
            )
        ).scalar()
        r12_all = db.execute(
            text("select count(*) from opinions where region_id=12")
        ).scalar()
        r12_gf = db.execute(
            text("select count(*) from opinions where region_id=12 and geo_filtered=true")
        ).scalar()
    assert gf == 73, gf
    assert deprecated == 12, deprecated
    # 大厂区净计数 == 22（44 全量 - 22 污染）；廊坊市净计数 == 全量 - 51 污染（实时采集会漂移）
    assert r1 == 22, r1
    assert r12 == r12_all - r12_gf, (r12, r12_all, r12_gf)
    assert r12_gf == 51, r12_gf


# ------------------------- B. events deprecated 支持 -------------------------
def test_deprecated_status_contract() -> None:
    # EVENT_STATUS_LABELS 含 deprecated/已废弃
    assert events_api.EVENT_STATUS_LABELS.get("deprecated") == "已废弃"
    # NEXT_EVENT_STATUS 支持 deprecated -> active 恢复路径
    assert events_api.NEXT_EVENT_STATUS.get("deprecated") == "active"
    # EventStatus Literal 已扩展含 deprecated（list_events 筛选可用）
    assert "deprecated" in get_args(EventStatus)


def test_events_deprecated_filter_and_recover() -> None:
    """直接调用 events 路由处理函数（绕过 TestClient 启动钩子，验证 deprecated 筛选与恢复逻辑）。

    测试库会话显式绑定 127.0.0.1，避免 localhost 在 psycopg 下优先解析 IPv6(::1) 导致的连接挂起。
    """
    from sqlalchemy.orm import sessionmaker
    from app.models.event import Event
    from app.models.user import User
    from app.schemas.event import EventStatusUpdate
    from starlette.requests import Request

    url = "postgresql+psycopg://opinion_user:opinion_pass@127.0.0.1:5433/opinion_test"
    eng = create_engine(url, pool_pre_ping=True)
    db = sessionmaker(bind=eng)()
    try:
        admin = db.query(User).filter(User.username == "admin").first()
        assert admin is not None, "测试库缺少 admin 用户"

        ev = Event(
            title="phase1b-deprecated-test",
            status="deprecated",
            risk_level="low",
            opinion_count=0,
            risk_score=0,
        )
        db.add(ev)
        db.flush()
        eid = ev.id
        db.commit()

        # 可筛选 status=deprecated（直接调用需把 Query() 默认值显式传实参，绕过 FastAPI 解析）
        resp = events_api.list_events(
            page=1, size=20, title=None, region_id=None, risk_level=None,
            risk_shadow_level=None, topic_category=None, event_status="deprecated",
            trend=None, heat_min=None, heat_max=None, db=db, _current_user=admin,
        )
        ids = [it.id for it in resp.items]
        assert eid in ids, "deprecated 事件未被 status=deprecated 筛选命中"

        # deprecated -> active 恢复，不产生 500（直接执行转换路径含审计写入）
        scope = {
            "type": "http",
            "method": "PATCH",
            "path": f"/api/events/{eid}/status",
            "headers": [(b"user-agent", b"pytest")],
            "client": ("127.0.0.1", 1234),
            "query_string": b"",
        }
        req = Request(scope)
        upd = events_api.update_event_status(
            eid, EventStatusUpdate(status="active"), req, db, admin
        )
        assert upd.status == "active", upd.status
    finally:
        try:
            db.rollback()
        except Exception:
            pass
        try:
            db.query(Event).filter(Event.id == eid).delete()
            db.commit()
        except Exception:
            db.rollback()
        db.close()
        eng.dispose()
