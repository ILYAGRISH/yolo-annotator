"""
Handler registry. A handler is a function (ctx, params) -> JSON-serialisable
result, registered under a method name:

    @handler("yolo.load_model")
    def load_model(ctx: Context, params: dict) -> dict: ...

inline=True handlers run on the reader thread, i.e. they are answered at once
even while a long job is busy — only for cheap calls (ping).
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Any, Callable


class Cancelled(Exception):
    """Raised by ctx.check_cancel() — the client cancelled this request."""


class BadRequest(Exception):
    """Wrong or missing params, missing file, ... — the caller's fault."""


class MissingPackage(Exception):
    """A required package (torch, ultralytics) is not installed in this env."""


@dataclass
class Handler:
    fn: Callable[["Context", dict], Any]
    inline: bool = False


REGISTRY: dict[str, Handler] = {}


def handler(name: str, inline: bool = False):
    def register(fn):
        REGISTRY[name] = Handler(fn, inline)
        return fn
    return register


def require(params: dict, key: str, type_: type):
    value = params.get(key)
    if not isinstance(value, type_):
        raise BadRequest(f"parameter '{key}' must be {type_.__name__}")
    return value


def import_or_explain(module: str):
    """Import a heavy package lazily; turn ImportError into MissingPackage
    with a message the user can act on."""
    try:
        return __import__(module)
    except ImportError as e:
        raise MissingPackage(
            f"'{module}' is not installed in this Python environment ({e}). "
            "Run setup_ml_env.bat, or choose an interpreter that has it "
            "in ML > ML Settings.") from e


class Context:
    """Per-request helper handed to the handler: progress events + cancel flag."""

    _PROGRESS_INTERVAL = 0.1        # s — at most ~10 progress events per second

    def __init__(self, request_id, send: Callable[[dict], None]):
        self.id = request_id
        self._send = send
        self._cancel = threading.Event()
        self._last_progress = 0.0

    def cancel(self) -> None:
        self._cancel.set()

    @property
    def cancelled(self) -> bool:
        return self._cancel.is_set()

    def check_cancel(self) -> None:
        if self._cancel.is_set():
            raise Cancelled()

    def progress(self, done: int, total: int, message: str = "") -> None:
        now = time.monotonic()
        if done < total and now - self._last_progress < self._PROGRESS_INTERVAL:
            return
        self._last_progress = now
        self._send({"event": "progress", "id": self.id,
                    "done": done, "total": total, "message": message})


# register the handlers (modules import the names defined above)
from ml_backend.handlers import debug, system, yolo  # noqa: E402,F401
