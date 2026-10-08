"""
Wire protocol between the annotator (client) and the ML backend (server).

Shared by both sides, so it must stay pure standard library and work on
Python 3.10+ (the ML environment may be older than the app environment).

Transport: one JSON object per line (UTF-8) — client → server on the child's
stdin, server → client on its stdout. Library chatter printed to stdout is
redirected to stderr by the server, so stdout carries protocol lines only.

Client → server
    {"id": 7, "method": "yolo.load_model", "params": {"path": "best.pt"}}
    {"id": 8, "method": "cancel", "params": {"target": 7}}

Server → client
    {"event": "ready", "protocol": 1, "pid": 1234, "python": "3.11.15"}
    {"event": "progress", "id": 7, "done": 3, "total": 10, "message": "..."}
    {"id": 7, "result": {...}}
    {"id": 7, "error": {"type": "cancelled" | "not_found" | "bad_request"
                                | "missing_package" | "exception",
                        "message": "...", "traceback": "..."}}

Every request gets exactly one final reply (result or error), even when it
is cancelled. Requests run one at a time in arrival order (GPU work is
serial anyway); "ping" and "cancel" are answered immediately, even while a
long job is running.
"""
from __future__ import annotations

import json

PROTOCOL_VERSION = 1

# error types
CANCELLED = "cancelled"
NOT_FOUND = "not_found"          # unknown method
BAD_REQUEST = "bad_request"      # malformed line / wrong params / missing file
MISSING_PACKAGE = "missing_package"  # torch / ultralytics not installed in the ML env
EXCEPTION = "exception"          # the handler raised


def encode(msg: dict) -> str:
    """One protocol line, newline included. ensure_ascii keeps it 7-bit safe."""
    return json.dumps(msg, ensure_ascii=True, separators=(",", ":")) + "\n"


def decode(line: str) -> dict:
    msg = json.loads(line)
    if not isinstance(msg, dict):
        raise ValueError("protocol message must be a JSON object")
    return msg
