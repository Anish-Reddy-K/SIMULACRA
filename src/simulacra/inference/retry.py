import asyncio
from collections.abc import Awaitable, Callable

from simulacra.inference.base import InferenceBackend
from simulacra.inference.types import GenerationRequest, GenerationResult

Sleep = Callable[[float], Awaitable[None]]


async def generate_with_retry(
    backend: InferenceBackend,
    request: GenerationRequest,
    retries: int = 2,
    backoff_s: float = 1.0,
    sleep: Sleep = asyncio.sleep,
) -> tuple[GenerationResult, int]:
    """Retry transport/runtime failures with exponential backoff.

    Returns the final result and the number of retries used. Invalid model output is
    not retried here: that policy belongs to the caller, which must count it.
    """
    result = await backend.generate(request)
    used = 0
    while not result.ok and used < retries:
        await sleep(backoff_s * (2**used))
        used += 1
        result = await backend.generate(request)
    return result, used
