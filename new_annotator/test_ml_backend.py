"""
ML backend tests — protocol server (ml_backend/) + Qt client (annotator/ml/)
Run: .venv/Scripts/python test_ml_backend.py

The backend is started with THIS interpreter (no torch needed): it checks the
plumbing — requests, progress, cancel, crash + restart, stop, bad paths.

Optional real-model check (skipped unless both are set):
    ML_TEST_PYTHON=C:/miniconda3/envs/yolo_hard/python.exe
    ML_TEST_MODEL=D:/Bbox_search/best.pt
"""
import os
import sys
import tempfile
import time
from pathlib import Path

# ── headless Qt, private settings ─────────────────────────────────────────────
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).parent))
_TMP = Path(tempfile.mkdtemp())
os.environ["ANNOTATOR_SETTINGS"] = str(_TMP / "settings.ini")

from PyQt6.QtCore import QCoreApplication, QEventLoop, QTimer
from PyQt6.QtWidgets import QApplication
_app = QApplication.instance() or QApplication(sys.argv)

# ── helpers ───────────────────────────────────────────────────────────────────
_pass = _fail = 0

def check(name: str, ok: bool):
    global _pass, _fail
    status = "PASS" if ok else "FAIL"
    print(f"  [{status}] {name}")
    if ok:
        _pass += 1
    else:
        _fail += 1

def section(title: str):
    print(f"\n--- {title} ---")

def wait(pred, timeout=20.0) -> bool:
    """Spin the Qt event loop until pred() or timeout."""
    end = time.monotonic() + timeout
    loop = QEventLoop()
    while not pred():
        if time.monotonic() > end:
            return False
        QTimer.singleShot(20, loop.quit)
        loop.exec()
    return True

def call(backend, method, params=None, timeout=60.0):
    """Synchronous request for tests: returns (Reply | None, progress list)."""
    box, progress = [], []
    backend.request(method, params, on_done=box.append,
                    on_progress=lambda d, t, m: progress.append((d, t, m)))
    wait(lambda: box, timeout)
    return (box[0] if box else None), progress

from annotator.ml import config
from annotator.ml.client import (BACKEND_EXITED, NOT_CONFIGURED, START_FAILED,
                                 STOPPED_ERR, MLBackend, format_info)
from ml_backend import protocol

PY = sys.executable


# ═════════════════════════════════════════════════════════════════════════════
section("1. Config")
# ═════════════════════════════════════════════════════════════════════════════
check("app_dir holds ml_backend/", (config.app_dir() / "ml_backend" / "server.py").is_file())
check("default interpreter is .venv-ml", config.ENV_DIR_NAME in str(config.default_python()))
config.set_saved_python(PY)
check("saved interpreter resolves", config.resolve_python() == Path(PY))
check("missing interpreter -> None", config.resolve_python(str(_TMP / "nope.exe")) is None)
config.set_autostart(True)
check("autostart round-trip", config.autostart() is True)
config.set_autostart(False)
check("settings went to the temp ini, not the registry",
      (_TMP / "settings.ini").is_file())


# ═════════════════════════════════════════════════════════════════════════════
section("2. Requests")
# ═════════════════════════════════════════════════════════════════════════════
be = MLBackend(python=PY)
states = []
be.state_changed.connect(states.append)

r, _ = call(be, "ping")
check("first request auto-starts the backend", r is not None and r.ok and r.result["pong"])
check("states: starting -> ready", states[:2] == ["starting", "ready"])
check("ready event carries protocol version",
      be.ready_info.get("protocol") == protocol.PROTOCOL_VERSION)

payload = {"text": "Привет, 世界", "n": [1, 2.5, None, True]}
r, _ = call(be, "debug.echo", payload)
check("echo round-trip keeps unicode and types", r.ok and r.result == payload)

r, prog = call(be, "debug.sleep", {"steps": 6, "delay": 0.05})
check("long job finishes", r.ok and r.result == {"steps": 6})
check("progress events arrive, last is 6/6", prog and prog[-1][:2] == (6, 6))

r, _ = call(be, "debug.noisy")
r2, _ = call(be, "ping")
check("stdout chatter does not break the protocol", r.ok and r2 is not None and r2.ok)
check("chatter ends up in the log", wait(lambda: any("C-level write" in l for l in be.log_tail), 5))

r, _ = call(be, "no.such.method")
check("unknown method -> not_found", r.error_type == protocol.NOT_FOUND)

r, _ = call(be, "debug.fail", {"message": "boom"})
check("handler exception -> exception + traceback",
      r.error_type == protocol.EXCEPTION and "boom" in r.message
      and "Traceback" in r.error.get("traceback", ""))

r, _ = call(be, "yolo.load_model", {"path": str(_TMP / "missing.pt")})
check("missing model file -> bad_request", r.error_type == protocol.BAD_REQUEST)
r, _ = call(be, "yolo.load_model", {})
check("missing parameter -> bad_request", r.error_type == protocol.BAD_REQUEST)

fake = _TMP / "fake.pt"
fake.write_bytes(b"not a model")
r, _ = call(be, "yolo.load_model", {"path": str(fake)})
try:
    import ultralytics  # noqa: F401
    has_ultra = True
except ImportError:
    has_ultra = False
if not has_ultra:
    check("no ultralytics in this env -> missing_package with a hint",
          r.error_type == protocol.MISSING_PACKAGE and "setup_ml_env" in r.message)

r, _ = call(be, "system.info")
rows = {label: (value, ok) for label, value, ok in format_info(r.result)}
check("system.info reports this Python", r.ok and r.result["python"] == ".".join(map(str, sys.version_info[:3])))
check("system.info: numpy found", rows["numpy"][1])
if not has_ultra:
    check("format_info flags missing ultralytics", rows["ultralytics"] == ("not installed", False))


# ═════════════════════════════════════════════════════════════════════════════
section("3. Cancel")
# ═════════════════════════════════════════════════════════════════════════════
done = []
rid = be.request("debug.sleep", {"steps": 100, "delay": 0.05}, on_done=done.append)
check("indicator busy while a job runs", wait(lambda: be.state == MLBackend.BUSY, 5))
queued = []
rid2 = be.request("debug.sleep", {"steps": 100, "delay": 0.05}, on_done=queued.append)
r, _ = call(be, "ping", timeout=2)
check("ping answered at once while a job runs", r is not None and r.ok)
be.cancel(rid2)
be.cancel(rid)
wait(lambda: done and queued, 10)
check("running job cancelled", done and done[0].error_type == protocol.CANCELLED)
check("queued job cancelled before start",
      queued and queued[0].error_type == protocol.CANCELLED and "before start" in queued[0].message)
check("indicator back to ready", wait(lambda: be.state == MLBackend.READY, 3))


# ═════════════════════════════════════════════════════════════════════════════
section("4. Crash and restart")
# ═════════════════════════════════════════════════════════════════════════════
pid1 = be.ready_info.get("pid")
killed, lost = [], []
be.request("debug.exit", {"code": 7}, on_done=killed.append)
be.request("debug.sleep", {"steps": 100, "delay": 0.05}, on_done=lost.append)   # queued behind it
wait(lambda: killed and lost, 15)
check("crash: the request that killed it gets backend_exited",
      killed and killed[0].error_type == BACKEND_EXITED)
check("crash: requests queued behind it are failed too",
      lost and lost[0].error_type == BACKEND_EXITED)
check("crash: state error, exit code in last_error",
      be.state == MLBackend.ERROR and "exit code 7" in be.last_error)
r, _ = call(be, "ping")
check("next request restarts the backend", r is not None and r.ok)
check("it is a new process", be.ready_info.get("pid") not in (None, pid1))


# ═════════════════════════════════════════════════════════════════════════════
section("5. Stop")
# ═════════════════════════════════════════════════════════════════════════════
stopped = []
be.request("debug.sleep", {"steps": 200, "delay": 0.05}, on_done=stopped.append)
wait(lambda: be.state == MLBackend.BUSY, 5)
t0 = time.monotonic()
be.stop()
check("stop() is quick even with a running job", time.monotonic() - t0 < 4)
check("pending job answered on stop",
      stopped and stopped[0].error_type in (protocol.CANCELLED, STOPPED_ERR))
check("state stopped, process gone", be.state == MLBackend.STOPPED and not be.running)
be.stop()
check("stop() twice is harmless", be.state == MLBackend.STOPPED)


# ═════════════════════════════════════════════════════════════════════════════
section("6. Bad interpreter")
# ═════════════════════════════════════════════════════════════════════════════
bad = MLBackend(python=str(_TMP / "no_python.exe"))
r, _ = call(bad, "ping", timeout=5)
check("missing interpreter -> not_configured reply", r is not None and r.error_type == NOT_CONFIGURED)
check("missing interpreter -> state error", bad.state == MLBackend.ERROR)

not_python = _TMP / "not_python.exe"
not_python.write_bytes(b"MZ garbage")
bad2 = MLBackend(python=str(not_python))
r, _ = call(bad2, "ping", timeout=10)
check("file that is not a program -> start_failed",
      r is not None and r.error_type in (START_FAILED, BACKEND_EXITED))


# ═════════════════════════════════════════════════════════════════════════════
section("7. Real YOLO model (optional)")
# ═════════════════════════════════════════════════════════════════════════════
ml_py, ml_model = os.environ.get("ML_TEST_PYTHON"), os.environ.get("ML_TEST_MODEL")
if ml_py and ml_model:
    real = MLBackend(python=ml_py)
    r, _ = call(real, "system.info", timeout=120)
    check("ML env: torch and ultralytics present",
          r.ok and r.result["packages"]["torch"]["version"] and r.result["packages"]["ultralytics"]["version"])
    r, _ = call(real, "yolo.load_model", {"path": ml_model}, timeout=120)
    check("model loads: task and classes", r.ok and r.result["task"] and r.result["classes"])
    r2, _ = call(real, "yolo.load_model", {"path": ml_model}, timeout=60)
    check("second load comes from the cache", r2.ok and r2.result["cached"])
    print(f"      {r.result['task']}, {len(r.result['classes'])} classes, {r.result['device']}")
    real.stop()
else:
    print("  (skipped: set ML_TEST_PYTHON and ML_TEST_MODEL)")

be.stop()
QCoreApplication.processEvents()


# ═════════════════════════════════════════════════════════════════════════════
section("8. Settings dialog")
# ═════════════════════════════════════════════════════════════════════════════
from PyQt6.QtWidgets import QDialog, QLabel
from annotator.ml.settings_dialog import MLSettingsDialog

config.set_saved_python("")                          # nothing saved, no .venv-ml here
dlg_be = MLBackend()
dlg = MLSettingsDialog(dlg_be)
if not config.default_python().is_file():
    check("no environment -> red hint about setup_ml_env.bat", "setup_ml_env" in dlg._env_hint.text())
dlg._python_edit.setText(PY)
check("typed interpreter is shown as found", PY.lower() in dlg._env_hint.text().lower())
dlg._check()
check("Check fills the info table", wait(lambda: dlg._info_grid.count() > 0, 60))
labels = [dlg._info_grid.itemAt(i).widget().text() for i in range(dlg._info_grid.count())
          if isinstance(dlg._info_grid.itemAt(i).widget(), QLabel)]
check("info table lists Python and torch", any("Python" in s for s in labels) and any("torch" in s for s in labels))
if not has_ultra:
    check("missing torch -> warning status", "PyTorch" in dlg._check_status.text())
check("buttons enabled again", dlg._check_btn.isEnabled() and dlg._load_btn.isEnabled())
dlg._model_edit.setText(str(_TMP / "missing.pt"))
dlg._load_model()
check("bad model path -> error shown", wait(lambda: "bad_request" in dlg._model_status.text(), 20))
dlg._autostart.setChecked(True)
dlg.done(QDialog.DialogCode.Accepted)
check("OK saves interpreter, autostart and model path",
      config.saved_python() == PY and config.autostart() and config.test_model().endswith("missing.pt"))
check("OK keeps the backend that runs the saved interpreter", dlg_be.running)
dlg2 = MLSettingsDialog(dlg_be)
dlg2._python_edit.setText(str(_TMP / "other.exe"))
dlg2.done(QDialog.DialogCode.Rejected)
check("Cancel keeps the saved interpreter", config.saved_python() == PY)
check("Cancel keeps a backend running the saved interpreter", dlg_be.running)
dlg_be.stop()
config.set_autostart(False)


# ═════════════════════════════════════════════════════════════════════════════
section("9. Main window integration")
# ═════════════════════════════════════════════════════════════════════════════
from annotator.app_settings import app_settings
app_settings().setValue("user_name", "Tester")       # no modal name prompt
from annotator.i18n import set_language
import annotator.ui.main_window as mw

set_language("EN")
win = mw.MainWindow()
titles = [a.text() for a in win.menuBar().actions()]
check("ML extension installed", win._ml is not None)
check("ML menu sits right before Help", "&ML" in titles and titles.index("&ML") == len(titles) - 2)
check("status indicator says off", win._ml._indicator.text() == "ML: off")
check("backend not started by default (autostart off)", not win._ml.backend.running)
set_language("RU")
win.retranslate()
check("indicator follows the language", win._ml._indicator.text() == "ML: выкл")
check("menu actions follow the language", win._ml._act_settings.text() == "Настройки ML…")
set_language("EN")
r, _ = call(win._ml.backend, "ping")
check("window's backend works", r is not None and r.ok)
check("indicator shows ready", win._ml._indicator.text() == "ML: ready")
win.close()
check("closing the window stops the backend", not win._ml.backend.running)

import annotator.ml.extension as ext
_orig_install = ext.install
ext.install = lambda w: (_ for _ in ()).throw(RuntimeError("broken extension"))
win2 = mw.MainWindow()
check("broken ML extension: the app still starts, ML disabled", win2._ml is None)
check("broken ML extension: no ML menu", "&ML" not in [a.text() for a in win2.menuBar().actions()])
win2.close()
ext.install = _orig_install


# ═════════════════════════════════════════════════════════════════════════════
# close every window: one left open is destroyed during interpreter shutdown,
# its app-wide key filter then crashes the process (random exit code 139)
from PyQt6.QtWidgets import QApplication as _QApp
for _w in _QApp.topLevelWidgets():
    _w.close()

print(f"\n{'=' * 60}\n  {_pass} passed, {_fail} failed\n{'=' * 60}")
sys.exit(1 if _fail else 0)
