from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from simulacra.benchmarks.runner import ResultRecord, Target
from simulacra.persistence.models import (
    BenchmarkEvent,
    BenchmarkResult,
    BenchmarkRun,
    BenchmarkSample,
)

MAX_SAMPLE_TEXT = 2000
TERMINAL = ("completed", "completed_with_errors", "failed", "cancelled")


def create_run(
    session: Session, stage: str, hardware: dict[str, Any], config: dict[str, Any]
) -> int:
    run = BenchmarkRun(
        stage=stage,
        status="running",
        hardware_json=hardware,
        config_json=config,
        started_at=datetime.now(UTC),
    )
    session.add(run)
    session.commit()
    return run.id


def set_status(session: Session, run_id: int, status: str, error: str | None = None) -> None:
    run = session.get(BenchmarkRun, run_id)
    if run is None:
        return
    run.status = status
    run.error = error
    if status in TERMINAL:
        run.finished_at = datetime.now(UTC)
    session.commit()


def update_progress(session: Session, run_id: int, op: str, done: int, total: int) -> None:
    run = session.get(BenchmarkRun, run_id)
    if run is not None:
        run.op, run.op_done, run.op_total = op, done, total
        session.commit()


def add_event(session: Session, run_id: int, message: str) -> None:
    session.add(BenchmarkEvent(run_id=run_id, message=message))
    session.commit()


def mark_interrupted(session: Session) -> int:
    """Crash recovery: runs left 'running' by a previous process can never finish."""
    stuck = session.scalars(select(BenchmarkRun).where(BenchmarkRun.status == "running")).all()
    for run in stuck:
        run.status, run.error = (
            "failed",
            "interrupted: the server stopped while this run was active",
        )
        run.finished_at = datetime.now(UTC)
        session.add(BenchmarkEvent(run_id=run.id, message="Run interrupted by a server restart"))
    session.commit()
    return len(stuck)


def save_records(
    session: Session, run_id: int, target: Target, records: list[ResultRecord]
) -> None:
    info = next((m for m in target.model_infos if m.name == target.model), None)
    for rec in records:
        row = BenchmarkResult(
            run_id=run_id,
            target_label=target.label,
            runtime_kind=target.runtime.kind.value,
            base_url=target.runtime.base_url,
            runtime_version=target.runtime.version,
            model=target.model,
            model_digest=info.digest if info else None,
            quantization=info.quantization if info else None,
            parameter_size=info.parameter_size if info else None,
            model_size_bytes=info.size_bytes if info else None,
            structured_mode=target.structured_mode,
            stage=rec.stage,
            evidence=rec.evidence,
            workload=rec.workload,
            concurrency=rec.concurrency,
            workload_hash=rec.workload_hash,
            metrics_json=rec.metrics.model_dump() if rec.metrics else None,
            diagnostics_json=[d.model_dump() for d in rec.diagnostics],
            compat_json=rec.compat.model_dump() if rec.compat else None,
            extras_json=rec.extras,
        )
        session.add(row)
        session.flush()
        for s in rec.samples:
            r = s.result
            session.add(
                BenchmarkSample(
                    result_id=row.id,
                    idx=s.index,
                    group=s.group,
                    status=s.status,
                    text=r.text[:MAX_SAMPLE_TEXT],
                    error=r.error,
                    total_ms=r.total_ms,
                    ttft_ms=r.ttft_ms,
                    prompt_tokens=r.prompt_tokens,
                    completion_tokens=r.completion_tokens,
                )
            )
    session.commit()


def results_for_run(session: Session, run_id: int) -> list[BenchmarkResult]:
    return list(
        session.scalars(
            select(BenchmarkResult)
            .where(BenchmarkResult.run_id == run_id)
            .order_by(BenchmarkResult.id)
        )
    )


def all_results(session: Session) -> list[BenchmarkResult]:
    return list(session.scalars(select(BenchmarkResult).order_by(BenchmarkResult.id)))


def samples_for_result(session: Session, result_id: int, limit: int = 500) -> list[BenchmarkSample]:
    return list(
        session.scalars(
            select(BenchmarkSample)
            .where(BenchmarkSample.result_id == result_id)
            .order_by(BenchmarkSample.idx)
            .limit(limit)
        )
    )
