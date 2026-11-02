import json
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ValidationError

from simulacra.inference.base import InferenceBackend
from simulacra.inference.types import GenerationRequest, GenerationResult

ValidationStatus = Literal["valid", "invalid_json", "schema_mismatch", "request_failed"]


@dataclass
class StructuredOutcome[T: BaseModel]:
    generation: GenerationResult
    status: ValidationStatus
    parsed: T | None = None
    detail: str | None = None

    @property
    def valid(self) -> bool:
        return self.status == "valid"


def validate_output[T: BaseModel](
    text: str, model: type[T]
) -> tuple[ValidationStatus, T | None, str | None]:
    """Strictly validate model output. Invalid output is reported, never silently repaired."""
    try:
        raw = json.loads(text)
    except json.JSONDecodeError as exc:
        return "invalid_json", None, str(exc)
    try:
        return "valid", model.model_validate(raw), None
    except ValidationError as exc:
        return "schema_mismatch", None, exc.errors()[0]["msg"] if exc.errors() else str(exc)


async def generate_structured[T: BaseModel](
    backend: InferenceBackend, request: GenerationRequest, model: type[T]
) -> StructuredOutcome[T]:
    """Ask for schema-constrained output, then validate it independently of the server."""
    req = request.model_copy(update={"json_schema": model.model_json_schema()})
    gen = await backend.generate(req)
    if not gen.ok:
        return StructuredOutcome(gen, "request_failed", detail=gen.error)
    status, parsed, detail = validate_output(gen.text, model)
    return StructuredOutcome(gen, status, parsed, detail)
