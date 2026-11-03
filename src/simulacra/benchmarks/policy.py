from pydantic import BaseModel, Field

POLICY_VERSION = "1"


class BalancedWeights(BaseModel):
    throughput: float = 0.4
    reliability: float = 0.3
    consistency: float = 0.3


class Policy(BaseModel):
    """Every threshold and weight the recommender uses. Documented in docs/benchmarks.md.

    Defaults are placeholders chosen before any baseline existed; they are meant to be
    reviewed against real results and are user-adjustable (stored in settings).
    """

    version: str = POLICY_VERSION
    safe_memory_fraction: float = Field(0.6, gt=0, le=1)  # peak server RSS / total RAM
    min_available_mb: float = 500.0  # system available memory must never drop below this
    max_swap_growth_mb: float = 1024.0
    min_valid_rate: float = Field(0.90, ge=0, le=1)  # structured-output validity floor
    max_failure_rate: float = Field(0.05, ge=0, le=1)  # request failure ceiling
    soak_min_seconds: float = 300.0  # shorter soaks are not enough evidence for "overnight"
    soak_min_drift: float = 0.8  # last-window / first-window throughput must stay above this
    balanced: BalancedWeights = BalancedWeights()
