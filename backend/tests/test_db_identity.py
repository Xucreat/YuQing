"""数据库身份安全门禁单元测试（Phase 7 生产身份解锁）。

覆盖 §4.E 要求的 7 个用例：
1. 正确 system_identifier + 正确库名 + opinions=52 -> VERIFIED + warning（低行数不再阻断）
2. system_identifier 不匹配 -> ABORTED
3. 数据库名不匹配 -> ABORTED
4. host/port 不匹配 -> ABORTED
5. recovery 状态异常 -> ABORTED
6. opinions >= 100 的正常生产身份 -> VERIFIED（无低行数 warning）
7. 测试库现有规则：DB_IDENTITY_CHECK=off 时门禁整体跳过（不连接、ok=True）

不连接任何真实数据库；使用内存 FakeEngine 注入 SQL 返回值。
"""
from types import SimpleNamespace

from app.core.db_identity import (
    ExpectedIdentity,
    _check_enabled,
    assert_identity_for_migration,
    verify_database_identity,
)

PROD_SID = "7663057120701798896"
PROD_DB = "opinion_db"


class _Result:
    def __init__(self, value):
        self._v = value

    def scalar(self):
        return self._v


class _Conn:
    def __init__(self, mapping):
        self._m = mapping

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, clause, *a, **k):
        sql = str(clause)
        for key, val in self._m.items():
            if key in sql:
                return _Result(val)
        return _Result(None)


class _Engine:
    def __init__(self, mapping, host="127.0.0.1", port=5432):
        self._m = mapping
        self.url = SimpleNamespace(host=host, port=port)

    def connect(self):
        return _Conn(self._m)


def _base_mapping(
    database=PROD_DB,
    sid=PROD_SID,
    recovery=False,
    opinions=52,
    alembic="d6_ai_review_consolidation",
    data_dir="",
):
    return {
        "current_database()": database,
        "SHOW data_directory": data_dir,
        "pg_control_system()": sid,
        "version_num FROM alembic_version": alembic,
        "pg_is_in_recovery()": recovery,
        "count(*) FROM opinions": opinions,
    }


def test_prod_low_opinions_verified_with_warning():
    """用例1：核心身份匹配但 opinions=52 < 100 -> VERIFIED + 低行数 WARNING。"""
    eng = _Engine(_base_mapping(opinions=52))
    res = verify_database_identity(eng, ExpectedIdentity())
    assert res.ok is True
    assert res.errors == []
    assert any("低于历史阈值" in w for w in res.warnings)
    assert any("不再阻断生产 migration" in w for w in res.warnings)


def test_system_identifier_mismatch_aborted():
    """用例2：system_identifier 不匹配 -> ABORTED。"""
    eng = _Engine(_base_mapping(sid="9999999999999999999"))
    res = verify_database_identity(eng, ExpectedIdentity())
    assert res.ok is False
    assert any("system_identifier" in e for e in res.errors)


def test_database_name_mismatch_aborted():
    """用例3：数据库名不匹配 -> ABORTED。"""
    eng = _Engine(_base_mapping(database="some_other_db"))
    res = verify_database_identity(eng, ExpectedIdentity())
    assert res.ok is False
    assert any("database" in e for e in res.errors)


def test_host_port_mismatch_aborted():
    """用例4：host/port 不匹配 -> ABORTED。"""
    eng = _Engine(_base_mapping(), host="10.0.0.5", port=5433)
    res = verify_database_identity(eng, ExpectedIdentity(host="127.0.0.1", port="5432"))
    assert res.ok is False
    assert any("host" in e or "port" in e for e in res.errors)


def test_recovery_state_aborted():
    """用例5：recovery 状态异常（只读从库）-> ABORTED。"""
    eng = _Engine(_base_mapping(recovery=True))
    res = verify_database_identity(eng, ExpectedIdentity())
    assert res.ok is False
    assert any("recovery" in e.lower() for e in res.errors)


def test_prod_normal_opinions_verified():
    """用例6：opinions >= 100 的正常生产身份 -> VERIFIED，无低行数 warning。"""
    eng = _Engine(_base_mapping(opinions=150))
    res = verify_database_identity(eng, ExpectedIdentity())
    assert res.ok is True
    assert res.errors == []
    assert not any("不再阻断生产 migration" in w for w in res.warnings)


def test_db_identity_check_off_skips(monkeypatch):
    """用例7：测试库现有规则 —— DB_IDENTITY_CHECK=off 时门禁整体跳过。"""
    monkeypatch.setenv("DB_IDENTITY_CHECK", "off")
    assert _check_enabled() is False
    # assert_identity_for_migration 在 off 时提前返回，不创建真实连接
    res = assert_identity_for_migration(
        database_url="postgresql+psycopg://x@127.0.0.1:5433/opinion_test"
    )
    assert res.ok is True
    assert any("未执行身份校验" in w for w in res.warnings)
