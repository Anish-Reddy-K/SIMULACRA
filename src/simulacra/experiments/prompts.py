"""Prompt construction. Shared scenario text comes first and the persona last, so runtimes
that cache prompt prefixes reuse the scenario across trials."""

import hashlib
from typing import Any

from simulacra.inference.types import Message

PROMPT_VERSION = "concept-v1"  # default variant; see VARIANTS

SYSTEM = (
    "You are role-playing a specific fictional consumer in a market research simulation. Answer as "
    "that person would, staying consistent with their finances, circumstances and traits. Do not "
    "be polite for its own sake: if the offer does not fit this person, say so. Respond only with "
    "the requested JSON."
)

INSTRUCTIONS_V1 = (
    "Give: purchase_intent (definitely, probably, unsure, probably_not or definitely_not), appeal "
    "(1-5), top_benefit (the main benefit this person sees), top_objection (the main reason for "
    "hesitation, or none), and reason (one sentence in the person's voice)."
)
# v2 asks for a shorter reason, which cuts generated tokens (the dominant cost of a trial).
INSTRUCTIONS_V2 = INSTRUCTIONS_V1.replace(
    "reason (one sentence in the person's voice)", "reason (one short sentence, under 15 words)"
)
VARIANTS = {"v1": ("concept-v1", INSTRUCTIONS_V1), "v2": ("concept-v2", INSTRUCTIONS_V2)}
INSTRUCTIONS = INSTRUCTIONS_V1


def scenario_text(scenario: dict[str, Any], treatment: dict[str, Any]) -> str:
    """Scenario fields overridden by the treatment's params (headline, price, description...)."""
    merged = {**scenario, **treatment}
    lines = [f"Product: {merged['product_name']}"]
    if merged.get("headline"):
        lines.append(f"Message shown to the person: {merged['headline']}")
    lines.append(f"What it is: {merged['description']}")
    if merged.get("price_usd") is not None:
        lines.append(f"Price: ${merged['price_usd']}")
    if merged.get("category"):
        lines.append(f"Category: {merged['category']}")
    return "\n".join(lines)


def build_messages(
    scenario: dict[str, Any], treatment: dict[str, Any], persona_card: str, variant: str = "v1"
) -> list[Message]:
    instructions = VARIANTS[variant][1]
    user = (
        f"OFFER\n{scenario_text(scenario, treatment)}\n\nPERSON\n{persona_card}\n\n{instructions}"
    )
    return [Message(role="system", content=SYSTEM), Message(role="user", content=user)]


def prompt_version(variant: str = "v1") -> str:
    return VARIANTS[variant][0]


def prompt_hash(variant: str = "v1") -> str:
    version, instructions = VARIANTS[variant]
    return hashlib.sha256(f"{version}|{SYSTEM}|{instructions}".encode()).hexdigest()[:12]


def flatten(messages: list[Message]) -> str:
    return "\n\n".join(f"[{m.role}]\n{m.content}" for m in messages)
