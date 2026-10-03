"""
Recent projects tests — storage list + File -> Open Recent menu
Run: .venv/Scripts/python test_recent.py
"""
import os
import sys
import tempfile
import shutil
from pathlib import Path

# ── headless Qt ───────────────────────────────────────────────────────────────
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).parent))

# Isolate app settings (recent list, language, user name) in a temp INI —
# the real user settings must never be touched by tests.
_settings_dir = tempfile.mkdtemp()
_settings_ini = str(Path(_settings_dir) / "settings.ini")
os.environ["ANNOTATOR_SETTINGS"] = _settings_ini

from PyQt6.QtWidgets import QApplication
_app = QApplication.instance() or QApplication(sys.argv)

# A known user name: otherwise opening a project asks for it in a modal dialog.
from annotator.app_settings import app_settings
app_settings().setValue("user_name", "Tester")

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


tmp = Path(tempfile.mkdtemp())


# ═════════════════════════════════════════════════════════════════════════════
# §1  recent_projects storage
# ═════════════════════════════════════════════════════════════════════════════
section("1. Storage")

from annotator.storage import recent_projects as rp

from annotator.app_settings import app_settings
check("settings redirected to temp INI", Path(app_settings().fileName()) == Path(_settings_ini))
rp.clear()
check("empty after clear", rp.load() == [])

a, b, c = tmp / "A.annproj", tmp / "B.annproj", tmp / "C.annproj"
rp.add(a)
check("single entry survives QSettings round-trip", rp.load() == [str(a.resolve())])
rp.add(b); rp.add(c)
check("most recent first", [Path(p).name for p in rp.load()] == ["C.annproj", "B.annproj", "A.annproj"])
rp.add(a)
check("re-opening moves to top, no duplicate",
      [Path(p).name for p in rp.load()] == ["A.annproj", "C.annproj", "B.annproj"])
if os.name == "nt":
    rp.add(str(b).upper())
    check("Windows: case-insensitive duplicate detection", len(rp.load()) == 3)
for i in range(15):
    rp.add(tmp / f"P{i}.annproj")
check(f"capped at {rp.MAX_RECENT}", len(rp.load()) == rp.MAX_RECENT)
check("cap keeps the newest", Path(rp.load()[0]).name == "P14.annproj")
rp.remove(tmp / "P14.annproj")
check("remove", Path(rp.load()[0]).name == "P13.annproj")
rp.clear()
check("clear", rp.load() == [])


# ═════════════════════════════════════════════════════════════════════════════
# §2  File -> Open Recent menu
# ═════════════════════════════════════════════════════════════════════════════
section("2. Menu")

import annotator.ui.main_window as mw
from annotator.controller.project_controller import ProjectController
from annotator.i18n import set_language, tr

warnings: list[str] = []
mw.QMessageBox.warning = lambda *a, **k: warnings.append(a[2] if len(a) > 2 else "")

# two real projects on disk
ctrl = ProjectController()
p1 = tmp / "Street.annproj"; ctrl.create_project("Street", p1)
p2 = tmp / "Field & Road.annproj"; ctrl.create_project("Field", p2)

win = mw.MainWindow()
menu = win._recent_menu

def entries():
    win._populate_recent_menu()
    return [a for a in menu.actions() if not a.isSeparator()]

e = entries()
check("empty list -> one disabled placeholder", len(e) == 1 and not e[0].isEnabled())

win._open_project_path(p1)
check("opening a project records it", rp.load() == [str(p1.resolve())])
win._open_project_path(p2)
e = entries()
check("two entries + 'Clear list'", len(e) == 3 and e[-1].text() == tr("act_clear_recent"))
check("label: number, name without .annproj, path",
      e[0].text().startswith("&1  Field && Road\t") and str(p2.resolve()).replace("&", "&&") in e[0].text())
check("tooltip is the plain path", e[0].toolTip() == str(p2.resolve()))

e[1].trigger()                                   # open "Street" from the menu
check("click opens that project", win._ctrl.project.name == "Street")
check("...and moves it to the top", Path(rp.load()[0]).name == "Street.annproj")

shutil.rmtree(p2)                                # project folder disappeared
e = entries()
missing = next(a for a in e if "Field" in a.text())
missing.trigger()
check("missing project -> warning shown", len(warnings) == 1)
check("missing project -> removed from list", all("Field" not in p for p in rp.load()))
check("current project untouched", win._ctrl.project.name == "Street")

new_dir = tmp / "Created.annproj"

class _FakeNewProjectDialog:                     # File -> New Project, accepted
    class DialogCode:
        Accepted = 1
    def __init__(self, parent=None):
        self.project_name, self.project_dir = "Created", str(new_dir)
    def exec(self):
        return 1

mw.NewProjectDialog = _FakeNewProjectDialog
win._new_project()
check("File -> New Project records it on top", Path(rp.load()[0]).name == "Created.annproj")

set_language("RU")
win.retranslate()
check("menu title translated (RU)", menu.title() == tr("menu_recent") and "недавние" in menu.title())
e = entries()
check("'Clear list' translated (RU)", e[-1].text() == "Очистить список")
set_language("EN")
win.retranslate()

e[-1].trigger()                                  # Clear list
check("Clear list empties it", rp.load() == [])

win.close()
shutil.rmtree(tmp, ignore_errors=True)
shutil.rmtree(_settings_dir, ignore_errors=True)


# ═════════════════════════════════════════════════════════════════════════════
print(f"\n{'=' * 60}\n  {_pass} passed, {_fail} failed\n{'=' * 60}")
sys.exit(1 if _fail else 0)
