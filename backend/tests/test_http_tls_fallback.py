import requests

from app.collectors import common


def test_http_get_uses_system_curl_after_ssl_failure(monkeypatch):
    class FailingSession:
        headers = {"User-Agent": "test-agent"}

        def get(self, *args, **kwargs):
            raise requests.exceptions.SSLError("incompatible TLS handshake")

    calls = {}

    def fake_run(command, **kwargs):
        calls["command"] = command
        calls["kwargs"] = kwargs
        return type(
            "Completed",
            (),
            {"returncode": 0, "stdout": b"<html>", "stderr": b""},
        )()

    monkeypatch.setattr(common.shutil, "which", lambda name: "curl.exe")
    monkeypatch.setattr(common.subprocess, "run", fake_run)

    assert common.http_get(FailingSession(), "https://example.test", timeout=7) == "<html>"
    assert calls["command"][0] == "curl.exe"
    assert "--location" in calls["command"]
    assert calls["command"][-1] == "https://example.test"
