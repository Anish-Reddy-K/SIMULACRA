from fastapi import APIRouter

from simulacra.inference.discovery import Discovery, discover
from simulacra.inference.types import ModelInfo

router = APIRouter(prefix="/lab")


@router.get("/runtimes")
async def runtimes() -> Discovery:
    """Installed runtime binaries and the servers answering right now."""
    return await discover()


class RuntimeModel(ModelInfo):
    runtime_base_url: str
    runtime_kind: str


@router.get("/models")
async def models() -> list[RuntimeModel]:
    found = await discover()
    return [
        RuntimeModel(**m.model_dump(), runtime_base_url=r.base_url, runtime_kind=r.info.kind.value)
        for r in found.runtimes
        if r.running and r.info
        for m in r.models
    ]
