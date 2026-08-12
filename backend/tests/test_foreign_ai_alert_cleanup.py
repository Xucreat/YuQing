from __future__ import annotations

from pathlib import Path
from importlib.util import module_from_spec, spec_from_file_location


class _Result:
    def __init__(self, value: int = 0):
        self.value = value

    def scalar_one(self) -> int:
        return self.value


class _Bind:
    def __init__(self):
        self.statements: list[str] = []

    def execute(self, statement):
        sql = str(statement)
        self.statements.append(sql)
        return _Result(3 if "foreign_alerts" in sql else 2 if "admissions" in sql else 1)


def test_cleanup_migration_deletes_only_retired_ai_workflow(monkeypatch):
    migration_path = Path(__file__).parents[1] / "alembic" / "versions" / "foreign_ai_alert_cleanup.py"
    spec = spec_from_file_location("foreign_ai_alert_cleanup_test_module", migration_path)
    assert spec and spec.loader
    migration = module_from_spec(spec)
    spec.loader.exec_module(migration)
    bind = _Bind()
    monkeypatch.setattr(migration.op, "get_bind", lambda: bind)

    migration.upgrade()

    assert "DELETE FROM foreign_alert_admission_actions" in bind.statements
    assert any(
        "DELETE FROM foreign_alerts" in sql
        and "evaluation_source = 'ai'" in sql
        and "foreign_ai_result_id IS NOT NULL" in sql
        for sql in bind.statements
    )
    assert "DELETE FROM foreign_alert_admissions" in bind.statements
    assert not any("foreign_ai_results" in sql and "DELETE" in sql for sql in bind.statements)
    assert bind.statements.index("DELETE FROM foreign_alert_admission_actions") < bind.statements.index("DELETE FROM foreign_alert_admissions")
