import hashlib


def stable_int(*parts: object) -> int:
    digest = hashlib.sha256("|".join(str(p) for p in parts).encode()).digest()
    return int.from_bytes(digest[:8], "big")


def assign_treatment(seed: int, persona_id: str, n_treatments: int) -> int:
    """Seeded random assignment that depends only on (seed, persona), never on order or run."""
    return stable_int("assign", seed, persona_id) % n_treatments


def trial_seed(seed: int, persona_id: str, treatment_idx: int, repeat_idx: int) -> int:
    return stable_int("trial", seed, persona_id, treatment_idx, repeat_idx) % (2**31 - 1)
