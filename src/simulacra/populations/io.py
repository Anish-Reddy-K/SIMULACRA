"""Import and export. Imported content is untrusted data: validated, bounded, never executed."""

import csv
import io
import json
from typing import Any

from pydantic import BaseModel, Field, ValidationError

MAX_IMPORT_BYTES = 20 * 1024 * 1024
MAX_FIELD_CHARS = 2000


class ImportError_(ValueError):
    pass


class PersonaRecord(BaseModel):
    """Strict import schema: unknown fields are rejected."""

    model_config = {"extra": "forbid"}

    synthetic_id: str = Field(min_length=1, max_length=40)
    name: str = Field(min_length=1, max_length=60)
    attributes: dict[str, str | int | float | bool]
    bio: str = Field(default="", max_length=MAX_FIELD_CHARS)
    interests: list[str] = Field(default_factory=list, max_length=10)
    brand_attitudes: str = Field(default="", max_length=MAX_FIELD_CHARS)
    quirk: str = Field(default="", max_length=MAX_FIELD_CHARS)
    # Present in Simulacra exports for provenance; ignored on import (never trusted).
    meta: dict[str, Any] = Field(default_factory=dict)


def export_jsonl(header: dict[str, Any], personas: list[dict[str, Any]]) -> str:
    lines = [json.dumps({"_simulacra_population": header}, sort_keys=True)]
    lines += [json.dumps(p, sort_keys=True) for p in personas]
    return "\n".join(lines) + "\n"


def export_csv(personas: list[dict[str, Any]]) -> str:
    if not personas:
        return ""
    attr_keys = sorted({k for p in personas for k in p["attributes"]})
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["synthetic_id", "name", *attr_keys, "bio"])
    for p in personas:
        row = [
            p["synthetic_id"],
            p["name"],
            *[p["attributes"].get(k, "") for k in attr_keys],
            p["bio"],
        ]
        w.writerow([_cell(c) for c in row])
    return out.getvalue()


def _cell(value: Any) -> str:
    """Neutralize spreadsheet formula injection in exported cells."""
    s = str(value)
    return (
        "'" + s
        if s[:1] in ("=", "+", "-", "@") and not s.lstrip("-").replace(".", "", 1).isdigit()
        else s
    )


def parse_jsonl(raw: bytes) -> tuple[dict[str, Any], list[PersonaRecord]]:
    if len(raw) > MAX_IMPORT_BYTES:
        raise ImportError_(f"file is larger than {MAX_IMPORT_BYTES // 2**20} MB")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ImportError_("file is not valid UTF-8 text") from exc
    header: dict[str, Any] = {}
    records: list[PersonaRecord] = []
    seen: set[str] = set()
    for n, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ImportError_(f"line {n}: not valid JSON") from exc
        if isinstance(obj, dict) and "_simulacra_population" in obj:
            header = (
                obj["_simulacra_population"]
                if isinstance(obj["_simulacra_population"], dict)
                else {}
            )
            continue
        try:
            rec = PersonaRecord.model_validate(obj)
        except ValidationError as exc:
            raise ImportError_(
                f"line {n}: {exc.errors()[0]['loc']} {exc.errors()[0]['msg']}"
            ) from exc
        if rec.synthetic_id in seen:
            raise ImportError_(f"line {n}: duplicate synthetic_id {rec.synthetic_id!r}")
        seen.add(rec.synthetic_id)
        records.append(rec)
    if not records:
        raise ImportError_("no personas found")
    return header, records
