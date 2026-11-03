"""Reusable experiment templates: starting points the UI fills in."""

from typing import Any

from simulacra.experiments.service import TreatmentIn


def ad_comparison(headlines: list[str]) -> list[TreatmentIn]:
    if not 2 <= len(headlines) <= 12 or any(not h.strip() for h in headlines):
        raise ValueError("an ad comparison needs 2 to 12 non-empty headlines")
    return [
        TreatmentIn(label=f"Headline {chr(65 + i)}", params={"headline": h.strip()})
        for i, h in enumerate(headlines)
    ]


def pricing(prices: list[float]) -> list[TreatmentIn]:
    if not 2 <= len(prices) <= 12 or len(set(prices)) != len(prices) or any(p < 0 for p in prices):
        raise ValueError("a pricing test needs 2 to 12 distinct non-negative prices")
    return [TreatmentIn(label=f"${p:g}", params={"price_usd": p}) for p in prices]


TEMPLATES: list[dict[str, Any]] = [
    {
        "id": "product_concept",
        "name": "Product concept",
        "description": "How do simulated people react to one offer? One baseline treatment.",
    },
    {
        "id": "ad_comparison",
        "name": "Ad comparison",
        "description": "Compare 2 or more headlines or messages for the same product. Each persona sees one, assigned at random.",
    },
    {
        "id": "pricing",
        "name": "Pricing",
        "description": "Compare simulated purchase interest at 2 or more prices. Each persona sees one price, assigned at random.",
    },
]
