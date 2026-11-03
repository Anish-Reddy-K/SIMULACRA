from simulacra.populations.spec import PopulationSpec

# Illustrative assumptions for demos and tests. These are NOT census data and make no claim
# of representativeness. Replace them with your own distributions for real work.
ASSUMED_ADULTS: dict[str, object] = {
    "name": "Assumed adult consumers",
    "description": "Illustrative distribution, not census data. Edit before real use.",
    "size": 100,
    "seed": 1,
    "attributes": {
        "age": {
            "kind": "numeric",
            "bins": [
                {"lo": 18, "hi": 25, "weight": 12},
                {"lo": 25, "hi": 35, "weight": 18},
                {"lo": 35, "hi": 50, "weight": 26},
                {"lo": 50, "hi": 65, "weight": 24},
                {"lo": 65, "hi": 85, "weight": 20},
            ],
        },
        "education": {
            "kind": "ordinal",
            "levels": ["no_degree", "high_school", "some_college", "bachelor", "graduate"],
            "weights": [8, 28, 22, 26, 16],
        },
        "income_band": {
            "kind": "ordinal",
            "levels": ["very_low", "low", "middle", "upper_middle", "high"],
            "weights": [14, 24, 30, 20, 12],
        },
        "tech_adoption": {
            "kind": "ordinal",
            "levels": ["laggard", "late_majority", "early_majority", "early_adopter", "innovator"],
            "weights": [14, 28, 34, 18, 6],
        },
        "price_sensitivity": {
            "kind": "ordinal",
            "levels": ["low", "moderate", "high", "very_high"],
            "weights": [15, 35, 35, 15],
        },
        "gender": {"kind": "categorical", "weights": {"woman": 50, "man": 49, "non_binary": 1}},
        "region": {
            "kind": "categorical",
            "weights": {"northeast": 17, "midwest": 21, "south": 38, "west": 24},
        },
        "employment": {
            "kind": "categorical",
            "weights": {
                "full_time": 48,
                "part_time": 12,
                "self_employed": 8,
                "student": 6,
                "unemployed": 5,
                "retired": 21,
            },
        },
        "household": {
            "kind": "categorical",
            "weights": {
                "lives_alone": 20,
                "couple": 28,
                "family_with_children": 32,
                "shared_housing": 12,
                "multigenerational": 8,
            },
        },
    },
    "correlations": [
        {"a": "education", "b": "income_band", "rho": 0.45},
        {"a": "age", "b": "tech_adoption", "rho": -0.35},
        {"a": "income_band", "b": "price_sensitivity", "rho": -0.40},
        {"a": "age", "b": "income_band", "rho": 0.20},
    ],
    "stratify_by": "region",
    "rules": ["graduate_needs_age", "student_low_income", "retired_age", "retired_not_student"],
}


def assumed_adults(size: int = 100, seed: int = 1) -> PopulationSpec:
    return PopulationSpec.model_validate({**ASSUMED_ADULTS, "size": size, "seed": seed})
