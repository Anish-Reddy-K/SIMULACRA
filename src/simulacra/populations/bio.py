"""Names, deterministic template biographies, and the contradiction checker."""

import re
from typing import Any

# Neutral given names, assigned at random. They carry no demographic signal on purpose.
FIRST_NAMES = [
    "Alex",
    "Jordan",
    "Taylor",
    "Morgan",
    "Casey",
    "Riley",
    "Avery",
    "Quinn",
    "Harper",
    "Rowan",
    "Sage",
    "Emerson",
    "Parker",
    "Dana",
    "Robin",
    "Skyler",
    "Jamie",
    "Cameron",
    "Drew",
    "Kendall",
    "Logan",
    "Reese",
    "Blake",
    "Charlie",
    "Devon",
    "Elliot",
    "Finley",
    "Hayden",
    "Jesse",
    "Kai",
    "Lane",
    "Marlow",
    "Noel",
    "Oakley",
    "Peyton",
    "Remy",
    "Shiloh",
    "Tatum",
    "Uri",
    "Val",
    "Wren",
    "Yael",
    "Zion",
    "Ari",
    "Bryn",
    "Cleo",
    "Dell",
    "Eden",
    "Frankie",
    "Gray",
    "Hollis",
]

INTEREST_BY_TECH = {
    "laggard": "simple, familiar products",
    "late_majority": "products that friends already use",
    "early_majority": "well-reviewed mainstream products",
    "early_adopter": "new gadgets and apps",
    "innovator": "cutting-edge technology",
}


def _h(value: Any) -> str:
    return str(value).replace("_", " ")


def describe(p: dict[str, Any]) -> str:
    return (
        f"{p['name']} is a {p['age']}-year-old {_h(p['gender'])} in the {p['region']} US region, "
        f"{_h(p['employment'])}, with {_h(p['education'])} education, {_h(p['income_band'])} "
        f"income and a household that is {_h(p['household'])}."
    )


def template_bio(p: dict[str, Any]) -> str:
    """Deterministic fallback bio built only from sampled facts (never invents new ones)."""
    tech = INTEREST_BY_TECH.get(str(p.get("tech_adoption")), "mainstream products")
    price = str(p.get("price_sensitivity", "moderate")).replace("_", " ")
    return f"{describe(p)} Tends toward {tech}, with {price} price sensitivity."


_AGE = re.compile(r"\b(\d{2})\s*(?:years?[ -]old|yo)\b|\bage[d]?\s+(\d{2})\b", re.I)
_BANNED = re.compile(
    r"\b(language model|as an ai|artificial intelligence|openai|anthropic|chatgpt)\b", re.I
)


def contradictions(bio: str, p: dict[str, Any]) -> list[str]:
    """Deterministic checks of an LLM-written bio against the sampled facts."""
    found: list[str] = []
    for m in _AGE.finditer(bio):
        stated = int(m.group(1) or m.group(2))
        if abs(stated - int(p["age"])) > 1:
            found.append(f"states age {stated} but the persona is {p['age']}")
    if _BANNED.search(bio):
        found.append("mentions being an AI or a model")
    emp = str(p.get("employment"))
    if emp == "retired" and re.search(r"\b(student|unemployed)\b", bio, re.I):
        found.append("contradicts retired status")
    if emp == "student" and re.search(r"\bretired\b", bio, re.I):
        found.append("contradicts student status")
    return found
