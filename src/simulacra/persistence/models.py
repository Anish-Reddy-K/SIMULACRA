from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Text
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
