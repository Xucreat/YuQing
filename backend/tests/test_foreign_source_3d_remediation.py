"""Sensitive-error regression matrix for foreign visualization APIs."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.api.foreign_visualization import _run
from app.services import foreign_visualization_service as visualization
from app.services.foreign_visualization_service import ForeignVisualizationError


METHODS = [
    visualization.get_dashboard_summary,
    visualization.get_dashboard_trends,
    visualization.get_dashboard_risk,
    visualization.get_dashboard_events,
    visualization.get_dashboard_alerts,
    visualization.get_dashboard_sources,
    visualization.get_hotwords,
    visualization.get_hotword_trends,
    visualization.get_hotword_sources,
    visualization.get_source_distribution,
    visualization.get_language_distribution,
]

SENSITIVE_ERRORS = [
    "password=hidden",
    "token=hidden",
    "secret=hidden",
    "proxy=http://user:password@example.test",
    "Traceback: internal path C:/private/app.py\nSELECT * FROM private_table",
]


class BrokenSession:
    def __init__(self, message: str):
        self.message = message

    def scalar(self, *args, **kwargs):
        raise RuntimeError(self.message)

    def scalars(self, *args, **kwargs):
        raise RuntimeError(self.message)

    def execute(self, *args, **kwargs):
        raise RuntimeError(self.message)


@pytest.mark.parametrize("method", METHODS, ids=lambda method: method.__name__)
@pytest.mark.parametrize("message", SENSITIVE_ERRORS)
def test_every_visualization_method_normalizes_sensitive_failures(method, message):
    with pytest.raises(ForeignVisualizationError) as raised:
        method(BrokenSession(message), days=1)
    assert raised.value.args == (ForeignVisualizationError.code,)
    assert message not in str(raised.value)


@pytest.mark.parametrize("method", METHODS, ids=lambda method: method.__name__)
@pytest.mark.parametrize("message", SENSITIVE_ERRORS)
def test_every_visualization_api_returns_same_safe_error(method, message):
    response = _run(lambda session: method(session, days=1), BrokenSession(message))
    assert response.status_code == 503
    payload = json.loads(response.body)
    assert payload["error_code"] == "FOREIGN_VISUALIZATION_QUERY_FAILED"
    assert payload["detail"] == "外网可视化数据暂时不可用"
    assert payload["request_id"]
    serialized = json.dumps(payload, ensure_ascii=False).casefold()
    assert message.casefold() not in serialized
    for forbidden in ("traceback", "select *", "password", "token", "secret", "proxy", "c:/private"):
        assert forbidden not in serialized


def test_frontend_visualization_errors_use_safe_allowlist():
    source = (Path(__file__).parents[1] / ".." / "frontend" / "src" / "views" / "ForeignWorkspace.vue").resolve().read_text(encoding="utf-8")
    start = source.index("function visualizationFailure")
    end = source.index("function markVisualizationFresh", start)
    block = source[start:end]
    assert "error_code" in block
    assert "response?.data?.detail" not in block
    assert "外网可视化数据暂时不可用" in block
