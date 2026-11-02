from typing import Literal

from pydantic import BaseModel, Field


class Sentiment(BaseModel):
    label: Literal["positive", "negative", "neutral"]


class PurchaseDecision(BaseModel):
    """Structured persona decision used by workloads B, C, D, F and G."""

    decision: Literal["buy_now", "consider_later", "pass"]
    likelihood: int = Field(ge=1, le=5)
    reason_code: Literal["price", "need", "budget", "trust", "features", "other"]
    main_reason: str = Field(max_length=300)


class DetailedReaction(BaseModel):
    """Larger nested schema for workload E (strict JSON conformity)."""

    decision: Literal["buy_now", "consider_later", "pass"]
    likelihood: int = Field(ge=1, le=5)
    objections: list[str] = Field(max_length=3)
    would_recommend: bool
    summary: str = Field(max_length=200)


class OwnershipCheck(BaseModel):
    owns_similar_product: bool
    reason: str = Field(max_length=200)
