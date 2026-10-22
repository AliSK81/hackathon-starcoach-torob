import json

from fastapi.testclient import TestClient

from starcoach.app import create_app
from starcoach.config import get_settings
from starcoach.logs import log_event


def test_health_and_index():
    client = TestClient(create_app(get_settings()))
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    page = client.get("/")
    assert page.status_code == 200
    assert 'dir="rtl"' in page.text


def test_log_event_appends_and_redacts(tmp_path):
    log_event(tmp_path, "runs", "a", api_key="secret", n=1)
    log_event(tmp_path, "runs", "b")
    lines = (tmp_path / "runs.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    first = json.loads(lines[0])
    assert first["api_key"] == "***" and first["n"] == 1
