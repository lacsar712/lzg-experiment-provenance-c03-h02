from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import authenticate_user, create_access_token, get_current_user, require_researcher
from app.cqrs import (
    ConflictError,
    DomainError,
    abort_run,
    attach_artifact,
    complete_run,
    list_events,
    record_metric,
    start_run,
)
from app.database import get_db
from app.models import RunProjection
from app.schemas import (
    AbortRunCommand,
    AttachArtifactCommand,
    CompleteRunCommand,
    EventOut,
    LineageOut,
    LoginRequest,
    RecordMetricCommand,
    RunOut,
    StartRunCommand,
    TokenResponse,
)

router = APIRouter(prefix="/api")


def _handle_domain(exc: DomainError) -> None:
    raise HTTPException(status_code=exc.status_code, detail=exc.message)


@router.get("/health")
def health():
    return {"status": "ok", "service": "experiment-provenance"}


@router.post("/auth/login", response_model=TokenResponse)
def login(body: LoginRequest):
    user = authenticate_user(body.username, body.password)
    if not user:
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    token = create_access_token(user["username"], user["role"])
    return TokenResponse(
        access_token=token,
        role=user["role"],
        username=user["username"],
    )


@router.get("/runs", response_model=list[RunOut])
def get_runs(
    project: str | None = Query(default=None),
    status: str | None = Query(default=None),
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    stmt = select(RunProjection).order_by(RunProjection.started_at.desc())
    if project:
        stmt = stmt.where(RunProjection.project == project)
    if status:
        stmt = stmt.where(RunProjection.status == status)
    return list(db.scalars(stmt).all())


@router.post("/runs", response_model=RunOut, status_code=201)
def create_run(
    body: StartRunCommand,
    db: Session = Depends(get_db),
    user: dict = Depends(require_researcher),
):
    try:
        return start_run(
            db,
            actor=user["username"],
            project=body.project,
            name=body.name,
            dataset_content_sha256=body.dataset_content_sha256,
            code_commit_sha=body.code_commit_sha,
            description=body.description,
            expected_version=body.expected_version,
        )
    except DomainError as exc:
        _handle_domain(exc)


@router.get("/runs/{run_id}", response_model=RunOut)
def get_run(
    run_id: UUID,
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    proj = db.get(RunProjection, run_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Run 不存在")
    return proj


@router.post("/runs/{run_id}/metrics", response_model=RunOut)
def post_metric(
    run_id: UUID,
    body: RecordMetricCommand,
    db: Session = Depends(get_db),
    user: dict = Depends(require_researcher),
):
    try:
        return record_metric(
            db,
            run_id=run_id,
            actor=user["username"],
            name=body.name,
            value=body.value,
            step=body.step,
            expected_version=body.expected_version,
        )
    except DomainError as exc:
        _handle_domain(exc)


@router.post("/runs/{run_id}/artifacts", response_model=RunOut)
def post_artifact(
    run_id: UUID,
    body: AttachArtifactCommand,
    db: Session = Depends(get_db),
    user: dict = Depends(require_researcher),
):
    try:
        return attach_artifact(
            db,
            run_id=run_id,
            actor=user["username"],
            name=body.name,
            uri=body.uri,
            content_sha256=body.content_sha256,
            media_type=body.media_type,
            expected_version=body.expected_version,
        )
    except DomainError as exc:
        _handle_domain(exc)


@router.post("/runs/{run_id}/complete", response_model=RunOut)
def post_complete(
    run_id: UUID,
    body: CompleteRunCommand,
    db: Session = Depends(get_db),
    user: dict = Depends(require_researcher),
):
    try:
        return complete_run(
            db,
            run_id=run_id,
            actor=user["username"],
            result_summary=body.result_summary,
            expected_version=body.expected_version,
        )
    except DomainError as exc:
        _handle_domain(exc)


@router.post("/runs/{run_id}/abort", response_model=RunOut)
def post_abort(
    run_id: UUID,
    body: AbortRunCommand,
    db: Session = Depends(get_db),
    user: dict = Depends(require_researcher),
):
    try:
        return abort_run(
            db,
            run_id=run_id,
            actor=user["username"],
            reason=body.reason,
            expected_version=body.expected_version,
        )
    except DomainError as exc:
        _handle_domain(exc)


@router.get("/runs/{run_id}/events", response_model=list[EventOut])
def get_events(
    run_id: UUID,
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    if not db.get(RunProjection, run_id):
        # allow reading events even if projection missing, but typically exists
        events = list_events(db, run_id)
        if not events:
            raise HTTPException(status_code=404, detail="Run 不存在")
        return events
    return list_events(db, run_id)


@router.get("/runs/{run_id}/lineage", response_model=LineageOut)
def get_lineage(
    run_id: UUID,
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    proj = db.get(RunProjection, run_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Run 不存在")
    return LineageOut(
        run_id=proj.id,
        project=proj.project,
        name=proj.name,
        status=proj.status,
        code_commit_sha=proj.code_commit_sha,
        dataset_content_sha256=proj.dataset_content_sha256,
        artifacts=proj.artifacts_json or [],
        metrics=proj.metrics_json or [],
        result_summary=proj.result_summary,
        abort_reason=proj.abort_reason,
        started_at=proj.started_at,
        finished_at=proj.finished_at,
        started_by=proj.started_by,
        version=proj.version,
    )
