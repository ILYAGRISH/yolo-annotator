"""
MLBackend — runs ml_backend.server in a child process (QProcess) and talks to
it with the JSON-lines protocol (ml_backend/protocol.py).

Everything is asynchronous and lives on the GUI thread: request() returns at
once, and the callbacks fire from Qt signals, so the UI never freezes.

    backend = MLBackend()
    rid = backend.request("yolo.load_model", {"path": p},
                          on_done=lambda r: print(r.ok, r.result or r.message),
                          on_progress=lambda done, total, msg: ...)
    backend.cancel(rid)

Every request gets exactly one on_done call — with an error Reply when the
backend fails to start, crashes or is stopped. A request on a stopped or
crashed backend (re)starts it.
"""
from __future__ import annotations

import collections
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from PyQt6.QtCore import QObject, QProcess, QProcessEnvironment, QTimer, pyqtSignal

from annotator.ml import config
from ml_backend import protocol

# client-side error types, in addition to protocol.*
NOT_CONFIGURED = "not_configured"     # no interpreter found
START_FAILED = "start_failed"         # interpreter missing / not Python / no ml_backend
BACKEND_EXITED = "backend_exited"     # process died while the request was pending
STOPPED_ERR = "stopped"               # stop() called while the request was pending

OnDone = Callable[["Reply"], None]
OnProgress = Callable[[int, int, str], None]


@dataclass
class Reply:
    id: int
    result: Any = None
    error: dict | None = None

    @property
    def ok(self) -> bool:
        return self.error is None

    @property
    def error_type(self) -> str:
        return (self.error or {}).get("type", "")

    @property
    def message(self) -> str:
        return (self.error or {}).get("message", "")


@dataclass
class _Pending:
    method: str
    on_done: OnDone | None
    on_progress: OnProgress | None
    line: str = field(repr=False, default="")


class MLBackend(QObject):
    STOPPED, STARTING, READY, BUSY, ERROR = "stopped", "starting", "ready", "busy", "error"

    state_changed = pyqtSignal(str)
    log_line = pyqtSignal(str)          # one line of the backend's stderr

    START_TIMEOUT_MS = 30_000
    STOP_TIMEOUT_MS = 5_000
    _QUIET = {"ping", "cancel"}         # do not make the indicator "busy"

    def __init__(self, parent=None, python: str | None = None):
        super().__init__(parent)
        self._python_override = python  # None = saved setting / .venv-ml
        self._proc: QProcess | None = None
        self._state = self.STOPPED
        self._next_id = 1
        self._pending: dict[int, _Pending] = {}
        self._outbox: list[str] = []    # lines written before the "ready" event
        self._buf = b""
        self._stopping = False
        self.ready_info: dict = {}      # the server's "ready" event
        self.last_error = ""
        self.log_tail: collections.deque[str] = collections.deque(maxlen=300)
        self._start_timer = QTimer(self, singleShot=True, interval=self.START_TIMEOUT_MS)
        self._start_timer.timeout.connect(self._on_start_timeout)

    # ── public API ────────────────────────────────────────────────────────────

    @property
    def state(self) -> str:
        return self._state

    @property
    def running(self) -> bool:
        return self._proc is not None and self._proc.state() != QProcess.ProcessState.NotRunning

    @property
    def python(self) -> Path | None:
        return config.resolve_python(self._python_override)

    def set_python(self, path: str | None) -> None:
        """Use another interpreter from the next start (None = saved setting)."""
        self._python_override = path

    def start(self) -> bool:
        """Start the backend if it is not running. False = could not even launch."""
        if self.running:
            return True
        python = self.python
        if python is None:
            self._fail_start(NOT_CONFIGURED,
                             "No ML Python environment: run setup_ml_env.bat or choose "
                             "an interpreter in ML > ML Settings.")
            return False
        server_pkg = config.app_dir() / "ml_backend"
        if not (server_pkg / "server.py").is_file():
            self._fail_start(START_FAILED, f"ml_backend not found in {config.app_dir()}")
            return False

        self._discard_proc()
        self.ready_info = {}
        self.last_error = ""
        self._buf = b""
        self._stopping = False
        proc = QProcess(self)
        proc.setProgram(str(python))
        proc.setArguments(["-u", "-m", "ml_backend.server"])
        proc.setWorkingDirectory(str(config.app_dir()))
        proc.setProcessEnvironment(self._environment(python))
        proc.readyReadStandardOutput.connect(self._on_stdout)
        proc.readyReadStandardError.connect(self._on_stderr)
        proc.finished.connect(self._on_finished)
        proc.errorOccurred.connect(self._on_error)
        self._proc = proc
        self._set_state(self.STARTING)
        self._log(f"[client] starting {python}")
        proc.start()
        self._start_timer.start()
        return True

    def stop(self) -> None:
        """Graceful shutdown (pending requests are answered as cancelled / stopped)."""
        proc = self._proc
        self._start_timer.stop()
        if proc is None:
            self._set_state(self.STOPPED)
            return
        self._stopping = True
        if proc.state() == QProcess.ProcessState.Running:
            proc.write(protocol.encode({"id": 0, "method": "shutdown"}).encode())
            if not proc.waitForFinished(self.STOP_TIMEOUT_MS):
                proc.kill()
                proc.waitForFinished(1000)
        elif proc.state() == QProcess.ProcessState.Starting:
            proc.kill()
            proc.waitForFinished(1000)
        self._on_stdout()                      # replies that arrived while blocking
        self._finish(STOPPED_ERR, "ML backend was stopped")
        self._set_state(self.STOPPED)

    def restart(self) -> bool:
        self.stop()
        return self.start()

    def request(self, method: str, params: dict | None = None,
                on_done: OnDone | None = None,
                on_progress: OnProgress | None = None) -> int:
        rid = self._next_id
        self._next_id += 1
        line = protocol.encode({"id": rid, "method": method, "params": params or {}})
        self._pending[rid] = _Pending(method, on_done, on_progress, line)
        if not self.running and not self.start():
            return rid                         # start() already failed it
        if self._state == self.STARTING:
            self._outbox.append(line)
        else:
            self._write(line)
        self._update_busy()
        return rid

    def cancel(self, rid: int) -> None:
        if rid in self._pending and self.running:
            line = protocol.encode({"id": -rid, "method": "cancel", "params": {"target": rid}})
            if self._state == self.STARTING:
                self._outbox.append(line)
            else:
                self._write(line)

    def pending_count(self) -> int:
        return sum(1 for p in self._pending.values() if p.method not in self._QUIET)

    # ── process I/O ───────────────────────────────────────────────────────────

    @staticmethod
    def _environment(python: Path) -> QProcessEnvironment:
        env = QProcessEnvironment.systemEnvironment()
        # keep the app's own environment out of the ML interpreter
        for var in ("PYTHONHOME", "PYTHONPATH", "VIRTUAL_ENV", "PYTHONSTARTUP"):
            env.remove(var)
        env.insert("PYTHONUNBUFFERED", "1")
        env.insert("PYTHONIOENCODING", "utf-8")
        env.insert("YOLO_VERBOSE", "False")    # ultralytics: no per-image chatter
        # conda environments keep DLLs in Library\bin and expect it on PATH
        lib_bin = python.parent / "Library" / "bin"
        if lib_bin.is_dir():
            env.insert("PATH", f"{lib_bin}{os.pathsep}{env.value('PATH')}")
        return env

    def _write(self, line: str) -> None:
        if self._proc is not None:
            self._proc.write(line.encode("utf-8"))

    def _on_stdout(self) -> None:
        if self._proc is None:
            return
        self._buf += bytes(self._proc.readAllStandardOutput())
        *lines, self._buf = self._buf.split(b"\n")
        for raw in lines:
            text = raw.decode("utf-8", "replace").strip()
            if not text:
                continue
            try:
                msg = protocol.decode(text)
            except ValueError:
                self._log(f"[client] not a protocol line: {text[:200]}")
                continue
            self._handle(msg)

    def _on_stderr(self) -> None:
        if self._proc is None:
            return
        data = bytes(self._proc.readAllStandardError()).decode("utf-8", "replace")
        for line in data.splitlines():
            if line.strip():
                self._log(line)

    def _handle(self, msg: dict) -> None:
        event = msg.get("event")
        if event == "ready":
            self._start_timer.stop()
            if msg.get("protocol") != protocol.PROTOCOL_VERSION:
                self.last_error = (f"ML backend speaks protocol {msg.get('protocol')}, "
                                   f"the app expects {protocol.PROTOCOL_VERSION}")
                self._finish(START_FAILED, self.last_error)
                self._kill_quietly()
                self._set_state(self.ERROR)
                return
            self.ready_info = msg
            self._set_state(self.READY)
            outbox, self._outbox = self._outbox, []
            for line in outbox:
                self._write(line)
            self._update_busy()
            return
        if event == "progress":
            p = self._pending.get(msg.get("id"))
            if p and p.on_progress:
                p.on_progress(int(msg.get("done", 0)), int(msg.get("total", 0)),
                              str(msg.get("message", "")))
            return
        rid = msg.get("id")
        if not isinstance(rid, int) or rid <= 0:   # replies to cancel (negative id) / shutdown
            return
        p = self._pending.pop(rid, None)
        if p is None:
            return
        self._update_busy()
        if p.on_done:
            p.on_done(Reply(rid, msg.get("result"), msg.get("error")))

    # ── process lifecycle ─────────────────────────────────────────────────────

    def _on_finished(self, code: int, status) -> None:
        self._start_timer.stop()
        self._on_stdout()
        if self._stopping:
            return                             # stop() finishes the bookkeeping
        tail = "\n".join(list(self.log_tail)[-8:])
        self.last_error = f"ML backend exited unexpectedly (exit code {code})"
        if tail:
            self.last_error += f"\n\n{tail}"
        self._finish(BACKEND_EXITED, self.last_error)
        self._set_state(self.ERROR)

    def _on_error(self, err) -> None:
        if err == QProcess.ProcessError.FailedToStart:
            self._start_timer.stop()
            msg = f"Cannot start {self.python}: {self._proc.errorString() if self._proc else err}"
            self._fail_start(START_FAILED, msg)

    def _on_start_timeout(self) -> None:
        self._fail_start(START_FAILED, f"ML backend did not start within "
                                       f"{self.START_TIMEOUT_MS // 1000} s")
        self._kill_quietly()

    def _fail_start(self, kind: str, message: str) -> None:
        self.last_error = message
        self._log(f"[client] {message}")
        # answer asynchronously: the caller of request() gets its id back first
        QTimer.singleShot(0, lambda: self._finish(kind, message))
        self._set_state(self.ERROR)

    def _discard_proc(self) -> None:
        """Forget a finished process object; its late signals must not reach us."""
        old, self._proc = self._proc, None
        if old is not None:
            for sig in (old.readyReadStandardOutput, old.readyReadStandardError,
                        old.finished, old.errorOccurred):
                try:
                    sig.disconnect()
                except TypeError:
                    pass
            old.deleteLater()

    def _kill_quietly(self) -> None:
        if self._proc is not None and self._proc.state() != QProcess.ProcessState.NotRunning:
            self._stopping = True
            self._proc.kill()
            self._proc.waitForFinished(1000)

    def _finish(self, kind: str, message: str) -> None:
        """Fail every pending request (each gets exactly one on_done)."""
        pending, self._pending = self._pending, {}
        self._outbox = []
        for rid, p in pending.items():
            if p.on_done:
                p.on_done(Reply(rid, error={"type": kind, "message": message}))

    def _update_busy(self) -> None:
        if self._state in (self.READY, self.BUSY):
            self._set_state(self.BUSY if self.pending_count() else self.READY)

    def _set_state(self, state: str) -> None:
        if state != self._state:
            self._state = state
            self.state_changed.emit(state)

    def _log(self, line: str) -> None:
        self.log_tail.append(line)
        self.log_line.emit(line)


def format_info(info: dict) -> list[tuple[str, str, bool]]:
    """system.info result -> [(label, value, ok)] rows for the settings dialog."""
    rows = [("Python", f"{info.get('python', '?')}   {info.get('executable', '')}", True)]
    pkgs = info.get("packages", {})
    for name in ("torch", "torchvision", "ultralytics", "numpy", "cv2"):
        p = pkgs.get(name, {})
        if p.get("version"):
            rows.append((name, str(p["version"]), True))
        else:
            rows.append((name, "not installed", name not in ("torch", "ultralytics")))
    dev = info.get("device", {})
    if dev.get("cuda"):
        gpus = ", ".join(f"{g['name']} ({g['memory_gb']} GB)" for g in dev.get("gpus", []))
        rows.append(("GPU", f"CUDA {dev.get('cuda_version')}: {gpus}", True))
    elif dev.get("mps"):
        rows.append(("GPU", "Apple MPS", True))
    elif pkgs.get("torch", {}).get("version"):
        rows.append(("GPU", "not available — models will run on the CPU (slow)", True))
    return rows


def dumps_pretty(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2)
