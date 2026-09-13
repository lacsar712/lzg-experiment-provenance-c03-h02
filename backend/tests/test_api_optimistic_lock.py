import hashlib

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import JSON, create_engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app


@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(_type, compiler, **kw):
    return "JSON"


def sha(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)

    def override_get_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    # Plain TestClient (no context manager) so the lifespan's create_all against
    # the real Postgres engine does not run; tables already exist on the SQLite
    # test engine above.
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture()
def token(client):
    resp = client.post(
        "/api/auth/login",
        json={"username": "researcher", "password": "lab123456"},
    )
    assert resp.status_code == 200
    return resp.json()["access_token"]


@pytest.fixture()
def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def start_run(client, headers, name="run"):
    resp = client.post(
        "/api/runs",
        headers=headers,
        json={
            "project": "p1",
            "name": name,
            "dataset_content_sha256": sha("ds"),
            "code_commit_sha": "abc1234",
            "expected_version": 0,
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_metric_stale_version_returns_409_and_appends_nothing(client, auth_headers):
    run = start_run(client, auth_headers)
    run_id = run["id"]
    assert run["version"] == 1

    # step 1: correct expected_version=1 -> 200, version 2
    ok = client.post(
        f"/api/runs/{run_id}/metrics",
        headers=auth_headers,
        json={"name": "acc", "value": 0.9, "step": 1, "expected_version": 1},
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["version"] == 2

    # step 2a: replay stale expected_version=1 -> must be 409
    stale1 = client.post(
        f"/api/runs/{run_id}/metrics",
        headers=auth_headers,
        json={"name": "acc", "value": 0.8, "step": 2, "expected_version": 1},
    )
    assert stale1.status_code == 409, stale1.text

    # step 2b: ancient expected_version=0 is rejected at schema layer -> 422,
    # but a stale-but-positive old value behaves the same semantically.
    future = client.post(
        f"/api/runs/{run_id}/metrics",
        headers=auth_headers,
        json={"name": "acc", "value": 0.8, "step": 2, "expected_version": 9},
    )
    assert future.status_code == 409, future.text

    # projection untouched: still version 2, still one metric
    detail = client.get(f"/api/runs/{run_id}", headers=auth_headers)
    assert detail.json()["version"] == 2
    assert len(detail.json()["metrics_json"]) == 1

    # event stream has no hole / no duplicate version
    events = client.get(f"/api/runs/{run_id}/events", headers=auth_headers).json()
    assert [(e["version"], e["event_type"]) for e in events] == [
        (1, "RunStarted"),
        (2, "MetricRecorded"),
    ]

    # correct version still works after the conflicts
    recovered = client.post(
        f"/api/runs/{run_id}/metrics",
        headers=auth_headers,
        json={"name": "acc", "value": 0.95, "step": 3, "expected_version": 2},
    )
    assert recovered.status_code == 200, recovered.text
    assert recovered.json()["version"] == 3


def test_all_command_paths_reject_stale_version_with_409(client, auth_headers):
    run = start_run(client, auth_headers, name="parity")
    run_id = run["id"]

    stale = {"expected_version": 99}  # current version is 1

    m = client.post(
        f"/api/runs/{run_id}/metrics",
        headers=auth_headers,
        json={"name": "m", "value": 1.0, "step": 0, **stale},
    )
    a = client.post(
        f"/api/runs/{run_id}/artifacts",
        headers=auth_headers,
        json={
            "name": "f.bin",
            "uri": "file:///tmp/f.bin",
            "content_sha256": sha("f"),
            "media_type": None,
            **stale,
        },
    )
    c = client.post(
        f"/api/runs/{run_id}/complete",
        headers=auth_headers,
        json={"result_summary": "done", **stale},
    )
    assert (m.status_code, a.status_code, c.status_code) == (409, 409, 409)

    events = client.get(f"/api/runs/{run_id}/events", headers=auth_headers).json()
    assert [e["event_type"] for e in events] == ["RunStarted"]
    detail = client.get(f"/api/runs/{run_id}", headers=auth_headers).json()
    assert detail["version"] == 1
    assert detail["status"] == "running"
