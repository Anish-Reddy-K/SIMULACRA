from typing import Literal

from pydantic import BaseModel, Field

PURCHASE_INTENTS = ("definitely", "probably", "unsure", "probably_not", "definitely_not")
BENEFITS = ("saves_time", "saves_money", "quality", "convenience", "fun", "status", "none")
OBJECTIONS = (
    "price",
    "trust",
    "need",
    "complexity",
    "privacy",
    "already_have_alternative",
    "none",
    "other",
)


class ConceptReaction(BaseModel):
    """Structured simulated reaction. The reason codes support analysis without embeddings."""

    purchase_intent: Literal["definitely", "probably", "unsure", "probably_not", "definitely_not"]
    appeal: int = Field(ge=1, le=5)
    top_benefit: Literal[
        "saves_time", "saves_money", "quality", "convenience", "fun", "status", "none"
    ]
    top_objection: Literal[
        "price",
        "trust",
        "need",
        "complexity",
        "privacy",
        "already_have_alternative",
        "none",
        "other",
    ]
    reason: str = Field(max_length=240)


TOP_BOX = ("definitely", "probably")
