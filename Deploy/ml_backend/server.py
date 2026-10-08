"""
ML backend server.  Started by the annotator as:

    <ml python> -u -m ml_backend.server          (cwd = new_annotator/)

Reads requests from stdin, answers on the ORIGINAL stdout (see protocol.py).
Exits when stdin closes — i.e. together with the app, even if it crashes.
"""
from __future__ import annotations

import os
import platform
import queue
import sys
import threading
import traceback

from ml_backend import protocol
from ml_backend.handlers import (REGISTRY, BadRequest, Cancelled, Context,
                                 MissingPackage)


class Channel:
    """The protocol streams = PRIVATE copies of the process's stdin / stdout.

    stdout: afterwards fd 1 and sys.stdout point at stderr, so anything a
    library prints (ultralytics banners, tqdm bars, C-level printf) lands in
    the log instead of corrupting the protocol.

    stdin: afterwards fd 0 is NUL. On Windows a thread blocked reading a pipe
    also blocks every other call on that pipe — and each DLL that loads
    (OpenCV, torch) queries the standard input handle while initialising its
    C runtime. Reading requests from the standard stdin therefore deadlocks
    the first `import cv2` in the worker thread; a private handle does not."""

    def __init__(self):
        sys.stdout.flush()
        proto_out = os.dup(1)
        proto_in = os.dup(0)
        os.dup2(2, 1)
        null = os.open(os.devnull, os.O_RDONLY)
        os.dup2(null, 0)
        os.close(null)
        if os.name == "nt":
            _point_std_handles_at_fds()
        sys.stdout = sys.stderr
        sys.stdin = open(os.devnull, encoding="utf-8")
        self._out = os.fdopen(proto_out, "w", encoding="utf-8", newline="\n")
        self._in = os.fdopen(proto_in, "rb")
        self._lock = threading.Lock()

    def lines(self):
        """Raw request lines until the client closes the pipe."""
        return iter(self._in.readline, b"")

    def send(self, msg: dict) -> None:
        line = protocol.encode(msg)          # may raise TypeError: caller handles
        with self._lock:
            self._out.write(line)
            self._out.flush()


def _point_std_handles_at_fds() -> None:
    """Make the Win32 STD_INPUT/OUTPUT handles follow fds 0 / 1 (= NUL / stderr):
    DLLs initialising their own C runtime read these handles, not CPython's fds."""
    import ctypes
    import msvcrt
    from ctypes import wintypes
    set_std = ctypes.windll.kernel32.SetStdHandle
    set_std.argtypes = [wintypes.DWORD, wintypes.HANDLE]
    set_std(wintypes.DWORD(-10 & 0xFFFFFFFF), msvcrt.get_osfhandle(0))   # STD_INPUT_HANDLE
    set_std(wintypes.DWORD(-11 & 0xFFFFFFFF), msvcrt.get_osfhandle(1))   # STD_OUTPUT_HANDLE


def _error(kind: str, message: str, tb: str = "") -> dict:
    err = {"type": kind, "message": message}
    if tb:
        err["traceback"] = tb
    return err


class Server:
    def __init__(self, channel: Channel):
        self.ch = channel
        self.jobs: queue.Queue = queue.Queue()
        self.active: dict = {}               # request id -> Context (queued / running)
        self.lock = threading.Lock()

    # ── main loop (reader thread = main thread) ────────────────────────────────

    SHUTDOWN_WAIT = 10.0                     # s for a running job to notice the cancel

    def run(self) -> None:
        worker = threading.Thread(target=self._work, name="ml-worker", daemon=True)
        worker.start()
        self.ch.send({"event": "ready", "protocol": protocol.PROTOCOL_VERSION,
                      "pid": os.getpid(), "python": platform.python_version(),
                      "executable": sys.executable})
        shutdown_id = None
        for raw in self.ch.lines():
            line = raw.decode("utf-8", "replace").strip()
            if not line:
                continue
            try:
                msg = protocol.decode(line)
            except ValueError as e:
                self.ch.send({"id": None, "error": _error(protocol.BAD_REQUEST, str(e))})
                continue
            if msg.get("method") == "shutdown":
                shutdown_id = msg.get("id")
                break
            self._dispatch(msg)

        # shutdown requested or stdin closed (app gone): cancel everything,
        # let the worker answer each queued / running request, then leave
        with self.lock:
            for ctx in self.active.values():
                ctx.cancel()
        self.jobs.put(None)
        worker.join(self.SHUTDOWN_WAIT)
        if shutdown_id is not None:
            self.ch.send({"id": shutdown_id, "result": {"ok": True}})

    def _dispatch(self, msg: dict) -> None:
        rid = msg.get("id")
        method = msg.get("method")
        params = msg.get("params") or {}
        if not isinstance(method, str) or not isinstance(params, dict):
            self.ch.send({"id": rid, "error": _error(
                protocol.BAD_REQUEST, "request needs a string 'method' and an object 'params'")})
            return

        if method == "cancel":
            with self.lock:
                ctx = self.active.get(params.get("target"))
            if ctx is not None:
                ctx.cancel()
            self.ch.send({"id": rid, "result": {"cancelled": ctx is not None}})
            return

        h = REGISTRY.get(method)
        if h is None:
            self.ch.send({"id": rid, "error": _error(
                protocol.NOT_FOUND, f"unknown method '{method}'")})
            return
        ctx = Context(rid, self.ch.send)
        if h.inline:
            self._execute(h, ctx, params)
        else:
            with self.lock:
                self.active[rid] = ctx
            self.jobs.put((h, ctx, params))

    # ── worker thread: one job at a time ───────────────────────────────────────

    def _work(self) -> None:
        while True:
            job = self.jobs.get()
            if job is None:                  # shutdown sentinel (queued after all jobs)
                return
            h, ctx, params = job
            try:
                if ctx.cancelled:            # cancelled while still queued
                    self.ch.send({"id": ctx.id, "error": _error(
                        protocol.CANCELLED, "cancelled before start")})
                else:
                    self._execute(h, ctx, params)
            finally:
                with self.lock:
                    self.active.pop(ctx.id, None)

    def _execute(self, h, ctx: Context, params: dict) -> None:
        try:
            result = h.fn(ctx, params)
            reply = {"id": ctx.id, "result": result}
            protocol.encode(reply)           # not JSON-serialisable -> exception below
        except Cancelled:
            reply = {"id": ctx.id, "error": _error(protocol.CANCELLED, "cancelled")}
        except BadRequest as e:
            reply = {"id": ctx.id, "error": _error(protocol.BAD_REQUEST, str(e))}
        except MissingPackage as e:
            reply = {"id": ctx.id, "error": _error(protocol.MISSING_PACKAGE, str(e))}
        except Exception as e:               # noqa: BLE001 — report, keep serving
            reply = {"id": ctx.id, "error": _error(
                protocol.EXCEPTION, f"{type(e).__name__}: {e}", traceback.format_exc())}
        self.ch.send(reply)


def main() -> int:
    channel = Channel()
    print(f"[ml_backend] started, python {platform.python_version()} "
          f"({sys.executable}), pid {os.getpid()}", file=sys.stderr, flush=True)
    Server(channel).run()
    print("[ml_backend] stopped", file=sys.stderr, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
