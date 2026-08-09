"""Static checks for the isolated foreign event workspace entry point."""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WORKSPACE = ROOT / "frontend" / "src" / "views" / "ForeignWorkspace.vue"
ROUTER = ROOT / "frontend" / "src" / "router" / "index.ts"


def test_foreign_events_tab_uses_foreign_workspace_and_foreign_apis_only():
    workspace = WORKSPACE.read_text(encoding="utf-8")
    router = ROUTER.read_text(encoding="utf-8")

    assert "value: 'events'" in workspace
    assert "query: { ...route.query, tab }" in workspace
    assert "api.get('/foreign/events/candidates'" in workspace
    assert "api.get('/foreign/events'" in workspace
    assert "api.post('/foreign/events/rebuild'" in workspace
    assert "'/events'" not in workspace
    assert "'/api/events'" not in workspace
    assert "path: '/foreign'" in router
    assert "ForeignWorkspace.vue" in router
