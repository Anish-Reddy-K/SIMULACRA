"""Compact, experiment-specific persona context (a token-budgeted prompt card)."""

from typing import Any

APPROX_CHARS_PER_TOKEN = 4
CORE_FIELDS = ("age", "gender", "region", "employment", "education", "income_band", "household")
PREFERENCE_FIELDS = ("tech_adoption", "price_sensitivity")


def build_card(
    persona: dict[str, Any], include: tuple[str, ...] = (), max_tokens: int = 300
) -> str:
    """Render a persona for a prompt, trimming the biography first if over budget.

    Token count is approximated (4 characters per token); the real tokenizer count is
    measured by the benchmark and run telemetry, not assumed here.
    """
    attrs = persona["attributes"]
    fields = [f for f in (*CORE_FIELDS, *PREFERENCE_FIELDS, *include) if f in attrs]
    lines = [f"{persona['name']} ({persona['synthetic_id']})"]
    lines += [
        f"- {f.replace('_', ' ')}: {str(attrs[f]).replace('_', ' ')}" for f in dict.fromkeys(fields)
    ]
    head = "\n".join(lines)
    budget = max_tokens * APPROX_CHARS_PER_TOKEN - len(head) - len("\nBackground: ")
    bio = persona.get("bio", "")
    if budget <= 0 or not bio:
        return head
    return f"{head}\nBackground: {bio[:budget].rstrip()}"


def approx_tokens(text: str) -> int:
    return -(-len(text) // APPROX_CHARS_PER_TOKEN)
