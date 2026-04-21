"""Run Telethon coroutines on a stable background event loop.

FastAPI sync route handlers run in AnyIO worker threads that do not own an
asyncio event loop. Telethon's async client expects a stable loop, so sync
ChatClient methods submit provider coroutines to this dedicated loop.
"""

from __future__ import annotations

import asyncio
import threading
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Coroutine


class _LoopState:
    loop: asyncio.AbstractEventLoop | None = None


_state = _LoopState()
_loop_lock = threading.Lock()


def _run_loop(loop: asyncio.AbstractEventLoop) -> None:
    asyncio.set_event_loop(loop)
    loop.run_forever()


def _ensure_loop() -> asyncio.AbstractEventLoop:
    with _loop_lock:
        if _state.loop is None or _state.loop.is_closed():
            loop = asyncio.new_event_loop()
            thread = threading.Thread(
                target=_run_loop,
                args=(loop,),
                name="telethon-client-loop",
                daemon=True,
            )
            thread.start()
            _state.loop = loop
        return _state.loop


def run_coroutine[T](coro: Coroutine[Any, Any, T], timeout: float = 300.0) -> T:
    """Run ``coro`` on the Telethon background loop and return its result."""
    future = asyncio.run_coroutine_threadsafe(coro, _ensure_loop())
    return future.result(timeout=timeout)
