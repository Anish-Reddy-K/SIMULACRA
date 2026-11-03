"""Population specification: marginal distributions, correlations, strata and hard rules.

A spec is plain data (JSON/YAML friendly) so populations are reviewable, versionable and
reproducible from (spec, seed). It makes assumptions explicit; it does not claim to
represent any real population.
"""

from typing import Annotated, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

MAX_POPULATION = 10_000


class Categorical(BaseModel):
    kind: Literal["categorical"] = "categorical"
    weights: dict[str, float] = Field(min_length=1)

    @field_validator("weights")
    @classmethod
    def positive(cls, v: dict[str, float]) -> dict[str, float]:
        if any(w < 0 for w in v.values()) or sum(v.values()) <= 0:
            raise ValueError("weights must be non-negative with a positive sum")
        return v


class Ordinal(BaseModel):
    """Ordered levels. May take part in correlations (via a Gaussian copula)."""

    kind: Literal["ordinal"] = "ordinal"
    levels: list[str] = Field(min_length=2)
    weights: list[float]

    @model_validator(mode="after")
    def aligned(self) -> "Ordinal":
        if len(self.weights) != len(self.levels):
            raise ValueError("weights must match levels")
        if any(w < 0 for w in self.weights) or sum(self.weights) <= 0:
            raise ValueError("weights must be non-negative with a positive sum")
        return self


class Bin(BaseModel):
    lo: float
    hi: float
    weight: float = Field(gt=0)

    @model_validator(mode="after")
    def ordered(self) -> "Bin":
        if self.hi <= self.lo:
            raise ValueError("bin hi must exceed lo")
        return self


class Numeric(BaseModel):
    """Numeric attribute from weighted bins, uniform within a bin. Integer valued."""

    kind: Literal["numeric"] = "numeric"
    bins: list[Bin] = Field(min_length=1)


Attribute = Annotated[Categorical | Ordinal | Numeric, Field(discriminator="kind")]


class Correlation(BaseModel):
    a: str
    b: str
    rho: float = Field(ge=-0.95, le=0.95)


class PopulationSpec(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    description: str = ""
    size: int = Field(ge=1, le=MAX_POPULATION)
    seed: int = 0
    attributes: dict[str, Attribute]
    correlations: list[Correlation] = []
    stratify_by: str | None = None  # categorical attribute whose shares are matched exactly
    rules: list[str] = []  # names of hard consistency rules (see rules.py)

    @model_validator(mode="after")
    def consistent(self) -> "PopulationSpec":
        for c in self.correlations:
            for name in (c.a, c.b):
                attr = self.attributes.get(name)
                if attr is None:
                    raise ValueError(f"correlation references unknown attribute {name!r}")
                if isinstance(attr, Categorical):
                    raise ValueError(f"{name!r} is categorical and cannot be correlated")
            if c.a == c.b:
                raise ValueError("a correlation needs two different attributes")
        if self.stratify_by is not None and not isinstance(
            self.attributes.get(self.stratify_by), Categorical
        ):
            raise ValueError("stratify_by must name a categorical attribute")
        return self
