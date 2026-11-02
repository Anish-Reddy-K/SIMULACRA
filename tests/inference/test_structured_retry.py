import json

import pytest
from pydantic import BaseModel

from simulacra.inference.mock import MockBackend
from simulacra.inference.retry import generate_with_retry
from simulacra.inference.structured import generate_structured, validate_output
from simulacra.inference.telemetry import Telemetry
from simulacra.inference.types import GenerationRequest, GenerationResult, Message

pytestmark = pytest.mark.anyio


class Decision(BaseModel):
    buy: bool
    reason: str


REQ = GenerationRequest(model="m", messages=[Message(role="user", content="q")])


def test_validate_output_classifies_failures() -> None:
    assert validate_output('{"buy": true, "reason": "x"}', Decision)[0] == "valid"
    assert validate_output("not json", Decision)[0] == "invalid_json"
    assert validate_output('{"buy": "maybe"}', Decision)[0] == "schema_mismatch"
    assert validate_output("[1,2]", Decision)[0] == "schema_mismatch"


async def test_generate_structured_valid_and_invalid_and_failed() -> None:
    good = MockBackend(lambda r: json.dumps({"buy": False, "reason": "no money"}))
    out = await generate_structured(good, REQ, Decision)
    assert out.valid and out.parsed == Decision(buy=False, reason="no money")

    bad = MockBackend(lambda r: "```json {oops```")
    out = await generate_structured(bad, REQ, Decision)
    assert out.status == "invalid_json" and out.parsed is None

    down = MockBackend(fail_every=1)
    assert (await generate_structured(down, REQ, Decision)).status == "request_failed"


async def test_schema_is_sent_to_the_backend() -> None:
    sent: list[dict[str, object] | None] = []

    def responder(r: GenerationRequest) -> str:
        sent.append(r.json_schema)
        return '{"buy": true, "reason": "r"}'

    await generate_structured(MockBackend(responder), REQ, Decision)
    assert sent[0] is not None and set(sent[0]["required"]) == {"buy", "reason"}  # type: ignore[call-overload]


async def test_retry_recovers_and_reports_retries() -> None:
    backend = MockBackend(fail_every=2)  # calls 2, 4, ... fail
    sleeps: list[float] = []

    async def fake_sleep(s: float) -> None:
        sleeps.append(s)

    await generate_with_retry(backend, REQ, sleep=fake_sleep)  # call 1 ok
    result, retries = await generate_with_retry(backend, REQ, sleep=fake_sleep)  # 2 fails, 3 ok
    assert result.ok and retries == 1 and sleeps == [1.0]


async def test_retry_gives_up_after_limit() -> None:
    sleeps: list[float] = []

    async def fake_sleep(s: float) -> None:
        sleeps.append(s)

    result, retries = await generate_with_retry(
        MockBackend(fail_every=1), REQ, retries=2, backoff_s=0.5, sleep=fake_sleep
    )
    assert not result.ok and retries == 2 and sleeps == [0.5, 1.0]


def test_telemetry_aggregates() -> None:
    t = Telemetry(window=3)
    assert t.failure_rate is None and t.latency_ms(0.5) is None
    for ms in (10, 20, 30, 40):
        t.record(GenerationResult(total_ms=ms, completion_tokens=10, decode_ms=100))
    t.record(GenerationResult(total_ms=5, error="x"))
    assert t.count == 3  # window evicts oldest
    assert t.failure_rate == pytest.approx(1 / 3)
    assert t.latency_ms(0.5) == 40
    assert t.median_decode_tokens_per_s == pytest.approx(100.0)
