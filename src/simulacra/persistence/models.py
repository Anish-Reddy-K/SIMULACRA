from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Index, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from simulacra.persistence.db import Base


class Setting(Base):
    """Key-value application settings. First table; proves the migration path."""

    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(primary_key=True)
    value: Mapped[str]


def _utcnow() -> datetime:
    return datetime.now(UTC)


class BenchmarkRun(Base):
    """One user-initiated benchmark across one or more targets."""

    __tablename__ = "benchmark_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    stage: Mapped[str]
    status: Mapped[str]  # running | completed | completed_with_errors | failed | cancelled
    hardware_json: Mapped[dict[str, Any]] = mapped_column(JSON)
    config_json: Mapped[dict[str, Any]] = mapped_column(JSON)
    op: Mapped[str | None]
    op_done: Mapped[int] = mapped_column(default=0)
    op_total: Mapped[int] = mapped_column(default=0)
    error: Mapped[str | None]


class BenchmarkResult(Base):
    __tablename__ = "benchmark_results"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(
        ForeignKey("benchmark_runs.id", ondelete="CASCADE"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    target_label: Mapped[str]
    runtime_kind: Mapped[str]
    base_url: Mapped[str]
    runtime_version: Mapped[str | None]
    model: Mapped[str]
    model_digest: Mapped[str | None]
    quantization: Mapped[str | None]
    parameter_size: Mapped[str | None]
    model_size_bytes: Mapped[int | None]
    structured_mode: Mapped[str]
    stage: Mapped[str]
    evidence: Mapped[str]
    workload: Mapped[str]
    concurrency: Mapped[int]
    workload_hash: Mapped[str | None]
    metrics_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    diagnostics_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    compat_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    extras_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class BenchmarkSample(Base):
    """Raw per-trial evidence behind every aggregate (inspectable in the UI)."""

    __tablename__ = "benchmark_samples"

    id: Mapped[int] = mapped_column(primary_key=True)
    result_id: Mapped[int] = mapped_column(
        ForeignKey("benchmark_results.id", ondelete="CASCADE"), index=True
    )
    idx: Mapped[int]
    group: Mapped[str]
    status: Mapped[str]
    text: Mapped[str] = mapped_column(Text)
    error: Mapped[str | None]
    total_ms: Mapped[float] = mapped_column(Float)
    ttft_ms: Mapped[float | None] = mapped_column(Float)
    prompt_tokens: Mapped[int | None]
    completion_tokens: Mapped[int | None]


class BenchmarkEvent(Base):
    """Append-only progress log; the source for the live progress stream."""

    __tablename__ = "benchmark_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(
        ForeignKey("benchmark_runs.id", ondelete="CASCADE"), index=True
    )
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    message: Mapped[str]


class Population(Base):
    __tablename__ = "populations"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class PopulationVersion(Base):
    """Immutable once status is 'ready'. Changing a population creates a new version."""

    __tablename__ = "population_versions"

    id: Mapped[int] = mapped_column(primary_key=True)
    population_id: Mapped[int] = mapped_column(
        ForeignKey("populations.id", ondelete="CASCADE"), index=True
    )
    version: Mapped[int]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    status: Mapped[str]  # generating | ready | failed
    source: Mapped[str]  # generated | imported
    spec_json: Mapped[dict[str, Any]] = mapped_column(JSON)
    seed: Mapped[int]
    size: Mapped[int]
    enrichment_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    diagnostics_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    progress_done: Mapped[int] = mapped_column(default=0)
    progress_total: Mapped[int] = mapped_column(default=0)
    error: Mapped[str | None]


class PersonaRow(Base):
    __tablename__ = "personas"

    id: Mapped[int] = mapped_column(primary_key=True)
    version_id: Mapped[int] = mapped_column(
        ForeignKey("population_versions.id", ondelete="CASCADE"), index=True
    )
    idx: Mapped[int]
    synthetic_id: Mapped[str]
    name: Mapped[str]
    attributes_json: Mapped[dict[str, Any]] = mapped_column(JSON)
    bio: Mapped[str] = mapped_column(Text)
    extras_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    meta_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class Run(Base):
    """A durable unit of long-running work made of leased batches (jobs)."""

    __tablename__ = "runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str]
    name: Mapped[str]
    state: Mapped[str]
    total_units: Mapped[int]
    done_units: Mapped[int] = mapped_column(default=0)
    error_units: Mapped[int] = mapped_column(default=0)
    config_json: Mapped[dict[str, Any]] = mapped_column(JSON)
    manifest_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error: Mapped[str | None]


class Job(Base):
    """One leased batch of units. Claimed transactionally; reclaimed if its lease expires."""

    __tablename__ = "jobs"
    __table_args__ = (
        UniqueConstraint("run_id", "batch_idx"),
        Index("ix_jobs_claim", "state", "lease_expires"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), index=True)
    batch_idx: Mapped[int]
    state: Mapped[str]  # pending | leased | done | failed | cancelled
    lease_owner: Mapped[str | None]
    lease_expires: Mapped[float | None] = mapped_column(Float)
    attempts: Mapped[int] = mapped_column(default=0)
    max_attempts: Mapped[int] = mapped_column(default=3)
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSON)
    last_error: Mapped[str | None]


class RunUnit(Base):
    """Result of one unit of work. The unique key makes result commits idempotent."""

    __tablename__ = "run_units"
    __table_args__ = (UniqueConstraint("run_id", "unit_idx"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), index=True)
    unit_idx: Mapped[int]
    status: Mapped[str]  # ok | error
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[float] = mapped_column(Float)


class RunEvent(Base):
    __tablename__ = "run_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), index=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    kind: Mapped[str]
    message: Mapped[str]


class WorkerRow(Base):
    __tablename__ = "workers"

    id: Mapped[str] = mapped_column(primary_key=True)
    pid: Mapped[int]
    started_at: Mapped[float] = mapped_column(Float)
    heartbeat_at: Mapped[float] = mapped_column(Float)
    stopped: Mapped[bool] = mapped_column(default=False)


class Experiment(Base):
    __tablename__ = "experiments"

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    name: Mapped[str]
    kind: Mapped[str]  # product_concept | ad_comparison | pricing
    research_question: Mapped[str] = mapped_column(Text)
    hypothesis: Mapped[str] = mapped_column(Text)
    population_version_id: Mapped[int] = mapped_column(ForeignKey("population_versions.id"))
    scenario_json: Mapped[dict[str, Any]] = mapped_column(JSON)
    config_json: Mapped[dict[str, Any]] = mapped_column(JSON)


class Treatment(Base):
    __tablename__ = "treatments"

    id: Mapped[int] = mapped_column(primary_key=True)
    experiment_id: Mapped[int] = mapped_column(
        ForeignKey("experiments.id", ondelete="CASCADE"), index=True
    )
    idx: Mapped[int]
    label: Mapped[str]
    params_json: Mapped[dict[str, Any]] = mapped_column(JSON)


class Trial(Base):
    """One persona x treatment x repeat. Raw prompt and output are kept for auditing."""

    __tablename__ = "trials"
    __table_args__ = (UniqueConstraint("run_id", "persona_id", "treatment_idx", "repeat_idx"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), index=True)
    persona_id: Mapped[str]  # synthetic id
    treatment_idx: Mapped[int]
    repeat_idx: Mapped[int]
    status: Mapped[str]  # valid | invalid_json | schema_mismatch | request_failed
    attempts: Mapped[int]
    prompt_text: Mapped[str] = mapped_column(Text)
    raw_output: Mapped[str] = mapped_column(Text)
    parsed_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    prompt_tokens: Mapped[int | None]
    completion_tokens: Mapped[int | None]
    latency_ms: Mapped[float] = mapped_column(Float)
    created_at: Mapped[float] = mapped_column(Float)


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    title: Mapped[str]
    computed_json: Mapped[dict[str, Any]] = mapped_column(JSON)
