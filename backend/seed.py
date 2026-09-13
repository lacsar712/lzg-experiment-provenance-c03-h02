"""Seed demo runs: 2 completed + 1 running."""

from __future__ import annotations

import hashlib
import time
from uuid import UUID

from sqlalchemy import select, text

from app.cqrs import attach_artifact, complete_run, record_metric, start_run
from app.database import Base, SessionLocal, engine
from app.models import RunProjection


def sha256_hex(text_value: str) -> str:
    return hashlib.sha256(text_value.encode("utf-8")).hexdigest()


def wait_for_db(max_attempts: int = 60) -> None:
    for i in range(max_attempts):
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return
        except Exception:
            time.sleep(1)
    raise RuntimeError("Database not ready")


def seed() -> None:
    wait_for_db()
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        existing = db.scalar(select(RunProjection).limit(1))
        if existing:
            print("Seed skipped: data already present")
            return

        # Completed run 1
        run1 = start_run(
            db,
            actor="researcher",
            project="protein-folding",
            name="AlphaFold baseline v1",
            dataset_content_sha256=sha256_hex("casp14-subset-v1"),
            code_commit_sha="a1b2c3d4e5f6789012345678abcdef0123456789"[:40],
            description="基线折叠实验，记录 TM-score",
            run_id=UUID("11111111-1111-1111-1111-111111111111"),
        )
        run1 = record_metric(
            db,
            run_id=run1.id,
            actor="researcher",
            name="tm_score",
            value=0.72,
            step=1,
            expected_version=run1.version,
        )
        run1 = record_metric(
            db,
            run_id=run1.id,
            actor="researcher",
            name="tm_score",
            value=0.81,
            step=2,
            expected_version=run1.version,
        )
        run1 = attach_artifact(
            db,
            run_id=run1.id,
            actor="researcher",
            name="structure.pdb",
            uri="s3://lab-artifacts/protein-folding/run1/structure.pdb",
            content_sha256=sha256_hex("structure-pdb-run1"),
            media_type="chemical/x-pdb",
            expected_version=run1.version,
        )
        complete_run(
            db,
            run_id=run1.id,
            actor="researcher",
            result_summary="基线完成，最终 TM-score=0.81",
            expected_version=run1.version,
        )

        # Completed run 2
        run2 = start_run(
            db,
            actor="researcher",
            project="drug-screen",
            name="Kinase panel screen #42",
            dataset_content_sha256=sha256_hex("kinase-panel-2024q3"),
            code_commit_sha="f0e1d2c3b4a5968778695a4b3c2d1e0f98765432",
            description="激酶抑制剂筛选批次",
            run_id=UUID("22222222-2222-2222-2222-222222222222"),
        )
        run2 = record_metric(
            db,
            run_id=run2.id,
            actor="researcher",
            name="hit_rate",
            value=0.12,
            step=1,
            expected_version=run2.version,
        )
        run2 = attach_artifact(
            db,
            run_id=run2.id,
            actor="researcher",
            name="hits.csv",
            uri="s3://lab-artifacts/drug-screen/run42/hits.csv",
            content_sha256=sha256_hex("hits-csv-run42"),
            media_type="text/csv",
            expected_version=run2.version,
        )
        complete_run(
            db,
            run_id=run2.id,
            actor="researcher",
            result_summary="筛选完成，命中率 12%",
            expected_version=run2.version,
        )

        # Running run 3
        run3 = start_run(
            db,
            actor="researcher",
            project="protein-folding",
            name="Fine-tune with MSA augmentation",
            dataset_content_sha256=sha256_hex("casp14-msa-aug-v2"),
            code_commit_sha="9abc8def7a6543210fedcba9876543210abcdef0",
            description="进行中的增强 MSA 微调实验",
            run_id=UUID("33333333-3333-3333-3333-333333333333"),
        )
        record_metric(
            db,
            run_id=run3.id,
            actor="researcher",
            name="loss",
            value=1.84,
            step=10,
            expected_version=run3.version,
        )

        print("Seed completed: 2 completed runs + 1 running run")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
