"""Compare a completed simulation run with real human responses (Phase 11 pipeline).

    uv run python scripts/evaluate_real_data.py --run 24 --csv real.csv --outcome would_buy \
        --positive yes,1,true --attributes region,age_band,income_band

The CSV has one row per real respondent: the outcome column plus segment columns whose names
and values match the simulation's (for example region=west, age_band=30-44). The result reports
agreement, calibration and failure modes, and is only meaningful with real data.
"""

import argparse
import json
import urllib.request
from pathlib import Path

from simulacra.evaluation import real_data as rd

API = "http://127.0.0.1:8765/api/v1"


def get(path: str) -> dict:  # type: ignore[type-arg]
    return json.load(urllib.request.urlopen(API + path, timeout=120))  # type: ignore[no-any-return]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", type=int, required=True)
    ap.add_argument("--csv", required=True)
    ap.add_argument("--outcome", required=True)
    ap.add_argument("--positive", default="1,yes,true")
    ap.add_argument("--attributes", required=True)
    ap.add_argument("--out")
    args = ap.parse_args()
    attrs = args.attributes.split(",")
    rows = rd.parse_real_csv(
        Path(args.csv).read_bytes(), args.outcome, set(args.positive.lower().split(","))
    )
    sim_segments = []
    for a in attrs:
        q = get(f"/runs/{args.run}/query?metric=top2_share&group_by={a}")
        sim_segments += [{"attribute": a, **r} for r in q["rows"] if not r["suppressed"]]
    overall_sim = get(f"/runs/{args.run}/query?metric=top2_share")["rows"][0]["value"]
    overall_real = sum(int(r[args.outcome]) for r in rows) / len(rows)
    obs = rd.segment_observations(rows, args.outcome, sim_segments, attrs)
    result = rd.evaluate(obs, overall_real, overall_sim)
    text = json.dumps(result, indent=2)
    if args.out:
        Path(args.out).write_text(text)
    print(text)


if __name__ == "__main__":
    main()
