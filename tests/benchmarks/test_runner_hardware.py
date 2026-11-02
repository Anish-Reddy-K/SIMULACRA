import pytest

from simulacra.benchmarks import workloads as wl
from simulacra.benchmarks.hardware import (
    detect_hardware,
    parse_metal,
    parse_pmset_batt,
    parse_pmset_settings,
)
from simulacra.benchmarks.runner import Target, run_target, run_trials
from simulacra.benchmarks.service import mock_responder
from simulacra.inference.mock import MockBackend


def test_parsers() -> None:
    assert parse_pmset_batt("Now drawing from 'Battery Power'") is True
    assert parse_pmset_batt("Now drawing from 'AC Power'") is False
    assert parse_pmset_batt("") is None
    assert parse_pmset_settings(" sleep 0 (sleep prevented by caffeinate)\n lowpowermode 1\n") == (
        True,
        True,
    )
    assert parse_pmset_settings(" sleep 10\n lowpowermode 0\n") == (False, False)
    assert parse_metal("      Metal Support: Metal 4") == "Metal 4"
    assert parse_metal(None) is None


def test_detect_hardware_has_basic_fields() -> None:
    hw = detect_hardware()
    assert hw.ram_total_mb > 0 and hw.disk_free_mb > 0 and hw.arch


async def _target(**kw: object) -> Target:
    backend = MockBackend(mock_responder, **kw)  # type: ignore[arg-type]
    return Target("mock / m", backend, "m", await backend.info(), pid=None)


pytestmark = pytest.mark.anyio


async def test_run_trials_respects_concurrency_and_order() -> None:
    t = await _target(latency_s=0.01)
    samples, wall, sampler = await run_trials(t, wl.workload_b("m", 12), concurrency=4)
    assert [s.index for s in samples] == list(range(12))
    assert all(s.status == "valid" for s in samples)
    assert wall < 12 * 0.01  # ran in parallel
    assert sampler.stats().samples >= 1


async def test_stage_screen_and_failed_compat() -> None:
    report = await run_target(await _target(), "screen")
    assert report.records[0].compat and report.records[0].compat.ok
    assert len(report.records) == 1

    down = await run_target(await _target(fail_every=1), "quick")
    assert down.skipped_reason and "compatibility" in down.skipped_reason
    assert len(down.records) == 1  # nothing else attempted


async def test_quick_stage_produces_expected_workloads() -> None:
    report = await run_target(await _target(latency_s=0.002), "quick")
    names = [(r.workload, r.concurrency) for r in report.records]
    assert names == [("compat", 1), ("B", 1), ("B", 4), ("E", 2), ("F", 2)]
    f = report.records[-1]
    assert f.diagnostics and all(r.evidence == "quick" for r in report.records[1:])
    assert f.workload_hash and f.metrics and f.metrics.n == len(f.samples)


async def test_detailed_stage_sweeps_and_repeats() -> None:
    report = await run_target(await _target(latency_s=0.002), "detailed")
    b = [r for r in report.records if r.workload == "B" and r.extras.get("role") != "repetition"]
    assert b[0].concurrency == 1 and len(b) >= 2
    reps = [r for r in report.records if r.extras.get("role") == "repetition"]
    assert len(reps) == 3 and reps[0].extras["repetition_cv"] is not None
    assert {"A", "C", "D", "E", "F"} <= {r.workload for r in report.records}


async def test_soak_records_windows_and_drift() -> None:
    report = await run_target(await _target(latency_s=0.002), "soak", soak_seconds=1.5)
    g = report.records[-1]
    assert g.workload == "G" and g.extras["windows"] and g.metrics and g.metrics.n > 10
    assert "duration_s" in g.extras
