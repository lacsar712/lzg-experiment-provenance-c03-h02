import hashlib
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.cqrs import (
    ConflictError,
    DomainError,
    abort_run,
    attach_artifact,
    complete_run,
    list_events,
    rebuild_projection_from_events,
    record_metric,
    start_run,
)
from app.database import Base
from app.models import RunProjection


def sha(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    # JSONB not available on SQLite — remap via create_all with JSON
    from sqlalchemy import JSON
    from sqlalchemy.dialects.postgresql import JSONB

    # For SQLite tests, compile JSONB as JSON
    from sqlalchemy.ext.compiler import compiles

    @compiles(JSONB, "sqlite")
    def _compile_jsonb_sqlite(_type, compiler, **kw):
        return "JSON"

    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()


def test_start_and_complete_happy_path(db):
    run = start_run(
        db,
        actor="researcher",
        project="p1",
        name="n1",
        dataset_content_sha256=sha("ds"),
        code_commit_sha="abc1234",
        description="d",
    )
    assert run.status == "running"
    assert run.version == 1

    run = record_metric(
        db,
        run_id=run.id,
        actor="researcher",
        name="acc",
        value=0.9,
        step=1,
        expected_version=1,
    )
    assert run.version == 2
    assert len(run.metrics_json) == 1

    run = complete_run(
        db,
        run_id=run.id,
        actor="researcher",
        result_summary="done",
        expected_version=2,
    )
    assert run.status == "completed"
    assert run.version == 3

    with pytest.raises(ConflictError):
        record_metric(
            db,
            run_id=run.id,
            actor="researcher",
            name="acc",
            value=0.95,
            step=2,
            expected_version=3,
        )


def test_metric_stale_expected_version_conflicts(db):
    run = start_run(
        db,
        actor="researcher",
        project="p1",
        name="n1",
        dataset_content_sha256=sha("ds2"),
        code_commit_sha="abc1234",
        description=None,
    )
    assert run.version == 1

    # expected_version=0 on an existing v1 run must conflict and append nothing
    with pytest.raises(ConflictError):
        record_metric(
            db,
            run_id=run.id,
            actor="researcher",
            name="loss",
            value=1.0,
            step=1,
            expected_version=0,
        )
    assert db.get(RunProjection, run.id).version == 1
    assert [e.event_type for e in list_events(db, run.id)] == ["RunStarted"]

    # a correct version advances to v2 ...
    run = record_metric(
        db,
        run_id=run.id,
        actor="researcher",
        name="loss",
        value=1.0,
        step=1,
        expected_version=1,
    )
    assert run.version == 2

    # ... and replaying the same stale version (1) conflicts without appending
    with pytest.raises(ConflictError):
        record_metric(
            db,
            run_id=run.id,
            actor="researcher",
            name="loss",
            value=2.0,
            step=2,
            expected_version=1,
        )
    with pytest.raises(ConflictError):
        record_metric(
            db,
            run_id=run.id,
            actor="researcher",
            name="loss",
            value=2.0,
            step=2,
            expected_version=0,
        )
    # a future/gap version must conflict too — no holes in the event stream
    with pytest.raises(ConflictError):
        record_metric(
            db,
            run_id=run.id,
            actor="researcher",
            name="loss",
            value=2.0,
            step=2,
            expected_version=9,
        )

    stored = db.get(RunProjection, run.id)
    assert stored.version == 2
    assert len(stored.metrics_json) == 1
    assert [(e.version, e.event_type) for e in list_events(db, run.id)] == [
        (1, "RunStarted"),
        (2, "MetricRecorded"),
    ]

    # session still usable after the conflicts; correct version goes through
    run = record_metric(
        db,
        run_id=run.id,
        actor="researcher",
        name="acc",
        value=0.9,
        step=2,
        expected_version=2,
    )
    assert run.version == 3


def test_metric_lock_parity_with_other_commands(db):
    """Stale expected_version on Metric must behave like Artifact/Complete/Abort."""
    run = start_run(
        db,
        actor="researcher",
        project="p1",
        name="n1",
        dataset_content_sha256=sha("ds-parity"),
        code_commit_sha="abc1234",
        description=None,
    )
    stale = 0  # current version is 1
    with pytest.raises(ConflictError):
        record_metric(
            db, run_id=run.id, actor="researcher", name="m", value=1.0, step=0,
            expected_version=stale,
        )
    with pytest.raises(ConflictError):
        attach_artifact(
            db, run_id=run.id, actor="researcher", name="a", uri="file:///x",
            content_sha256=sha("a"), media_type=None, expected_version=stale,
        )
    with pytest.raises(ConflictError):
        complete_run(
            db, run_id=run.id, actor="researcher",
            result_summary="done", expected_version=stale,
        )
    with pytest.raises(ConflictError):
        abort_run(
            db, run_id=run.id, actor="researcher",
            reason="x", expected_version=stale,
        )
    # nothing landed through any path
    assert db.get(RunProjection, run.id).version == 1
    assert [e.event_type for e in list_events(db, run.id)] == ["RunStarted"]


def test_abort_terminal(db):
    run = start_run(
        db,
        actor="researcher",
        project="p1",
        name="n1",
        dataset_content_sha256=sha("ds3"),
        code_commit_sha="abc1234",
        description=None,
    )
    run = abort_run(
        db,
        run_id=run.id,
        actor="researcher",
        reason="OOM",
        expected_version=1,
    )
    assert run.status == "aborted"
    with pytest.raises(ConflictError):
        complete_run(
            db,
            run_id=run.id,
            actor="researcher",
            result_summary="nope",
            expected_version=2,
        )


def test_projection_matches_event_replay(db):
    run = start_run(
        db,
        actor="researcher",
        project="p1",
        name="n1",
        dataset_content_sha256=sha("ds4"),
        code_commit_sha="deadbeef",
        description="x",
        run_id=uuid4(),
    )
    run = record_metric(
        db,
        run_id=run.id,
        actor="researcher",
        name="f1",
        value=1.5,
        step=0,
        expected_version=run.version,
    )
    run = attach_artifact(
        db,
        run_id=run.id,
        actor="researcher",
        name="model.bin",
        uri="file:///tmp/model.bin",
        content_sha256=sha("model"),
        media_type="application/octet-stream",
        expected_version=run.version,
    )
    run = complete_run(
        db,
        run_id=run.id,
        actor="researcher",
        result_summary="ok",
        expected_version=run.version,
    )

    events = list_events(db, run.id)
    assert [e.event_type for e in events] == [
        "RunStarted",
        "MetricRecorded",
        "ArtifactAttached",
        "RunCompleted",
    ]

    rebuilt = rebuild_projection_from_events(db, run.id)
    stored = db.get(RunProjection, run.id)
    assert rebuilt is not None and stored is not None
    assert rebuilt.status == stored.status
    assert rebuilt.version == stored.version
    assert rebuilt.dataset_content_sha256 == stored.dataset_content_sha256
    assert rebuilt.code_commit_sha == stored.code_commit_sha
    assert len(rebuilt.metrics_json) == len(stored.metrics_json)
    assert len(rebuilt.artifacts_json) == len(stored.artifacts_json)


def test_cannot_command_before_start(db):
    missing = uuid4()
    with pytest.raises(DomainError):
        record_metric(
            db,
            run_id=missing,
            actor="researcher",
            name="x",
            value=1,
            step=0,
            expected_version=0,
        )
