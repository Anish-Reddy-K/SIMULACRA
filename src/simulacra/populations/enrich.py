"""LLM enrichment: a short biography and quirks written around already-sampled facts.

The LLM never chooses demographics. Its output is validated and checked for contradictions;
if it cannot produce a consistent bio the deterministic template is used and flagged.
"""

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from pydantic import BaseModel, Field

from simulacra.inference.base import InferenceBackend
from simulacra.inference.structured import generate_structured
from simulacra.inference.types import GenerationRequest, Message
from simulacra.populations.bio import contradictions, describe, template_bio

MAX_ATTEMPTS = 2

SYSTEM = (
    "You write short, realistic fictional personal profiles for consumer-research simulations. "
    "Use ONLY the facts given; do not change them or add contradicting facts. Never mention AI. "
    "Respond only with the requested JSON."
)


class Enrichment(BaseModel):
    bio: str = Field(min_length=20, max_length=500)
    interests: list[str] = Field(min_length=2, max_length=5)
    brand_attitudes: str = Field(max_length=200)
    quirk: str = Field(max_length=150)


def _request(model: str, persona: dict[str, Any], seed: int) -> GenerationRequest:
    user = (
        f"FACTS (do not change): {describe(persona)}\n"
        f"Tech adoption: {persona['tech_adoption']}. "
        f"Price sensitivity: {persona['price_sensitivity']}.\n"
        "Write: bio (2-3 sentences, third person), interests (2-5 short items), brand_attitudes "
        "(one sentence about how they relate to brands), quirk (one small distinctive habit)."
    )
    return GenerationRequest(
        model=model,
        max_tokens=300,
        temperature=0.8,
        seed=seed,
        messages=[Message(role="system", content=SYSTEM), Message(role="user", content=user)],
    )


async def enrich_persona(
    backend: InferenceBackend, model: str, persona: dict[str, Any], seed: int
) -> dict[str, Any]:
    """Returns the fields to merge into the persona plus generation metadata."""
    problems: list[str] = []
    for attempt in range(MAX_ATTEMPTS):
        outcome = await generate_structured(
            backend, _request(model, persona, seed + attempt), Enrichment
        )
        if not outcome.valid or outcome.parsed is None:
            problems.append(f"attempt {attempt + 1}: {outcome.status}")
            continue
        found = contradictions(outcome.parsed.bio, persona)
        if found:
            problems.append(f"attempt {attempt + 1}: {'; '.join(found)}")
            continue
        return {
            "bio": outcome.parsed.bio,
            "interests": outcome.parsed.interests,
            "brand_attitudes": outcome.parsed.brand_attitudes,
            "quirk": outcome.parsed.quirk,
            "meta": {"enrichment": "llm", "model": model, "attempts": attempt + 1},
        }
    return {
        "bio": template_bio(persona),
        "interests": [],
        "brand_attitudes": "",
        "quirk": "",
        "meta": {"enrichment": "template_fallback", "model": model, "problems": problems},
    }


async def enrich_all(
    backend: InferenceBackend,
    model: str,
    personas: list[dict[str, Any]],
    seed: int,
    concurrency: int = 1,
    on_progress: Callable[[int, int], Awaitable[None]] | None = None,
) -> list[dict[str, Any]]:
    sem = asyncio.Semaphore(concurrency)
    out: list[dict[str, Any] | None] = [None] * len(personas)
    done = 0

    async def one(i: int) -> None:
        nonlocal done
        async with sem:
            out[i] = await enrich_persona(backend, model, personas[i], seed + i * 7)
        done += 1
        if on_progress:
            await on_progress(done, len(personas))

    await asyncio.gather(*(one(i) for i in range(len(personas))))
    return [o for o in out if o is not None]
