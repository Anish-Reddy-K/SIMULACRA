"""Hard consistency rules applied by rejection sampling. Each is a named, documented predicate."""

from collections.abc import Callable
from typing import Any

Persona = dict[str, Any]

LEVEL_RANK = {
    "no_degree": 0,
    "high_school": 1,
    "some_college": 2,
    "bachelor": 3,
    "graduate": 4,
    "very_low": 0,
    "low": 1,
    "middle": 2,
    "upper_middle": 3,
    "high": 4,
}


def _rank(value: Any) -> int:
    return LEVEL_RANK.get(str(value), 0)


RULES: dict[str, Callable[[Persona], bool]] = {
    # A graduate degree before 24 is implausible for this simulation's purposes.
    "graduate_needs_age": lambda p: (
        not (p.get("education") == "graduate" and p.get("age", 99) < 24)
    ),
    # Students and the unemployed do not sit in the top income bands.
    "student_low_income": lambda p: (
        not (p.get("employment") in ("student", "unemployed") and _rank(p.get("income_band")) > 2)
    ),
    "retired_age": lambda p: not (p.get("employment") == "retired" and p.get("age", 99) < 55),
    "retired_not_student": lambda p: (
        not (p.get("employment") == "student" and p.get("age", 0) > 60)
    ),
}
