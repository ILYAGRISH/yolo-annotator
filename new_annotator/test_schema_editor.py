"""
Class Schema Editor tests — deleting / reordering classes
Run: .venv/Scripts/python test_schema_editor.py
"""
import os
import sys
import tempfile
from pathlib import Path

# ── headless Qt ───────────────────────────────────────────────────────────────
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).parent))
os.environ["ANNOTATOR_SETTINGS"] = str(Path(tempfile.mkdtemp()) / "settings.ini")

from PyQt6.QtWidgets import QApplication, QDialog
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

from annotator.domain.label_class import LabelClass, SkeletonKeypoint
from annotator.ui.dialogs import class_delete_dialog
from annotator.ui.dialogs.class_schema_editor import ClassSchemaEditorDialog


class _FakeDeleteDialog:
    """Stands in for the modal ClassDeleteDialog: answers 'delete_all' or Cancel."""
    accept = True

    def __init__(self, *args, **kwargs):
        self.action, self.reassign_to = "delete_all", None

    def exec(self):
        return (QDialog.DialogCode.Accepted if _FakeDeleteDialog.accept
                else QDialog.DialogCode.Rejected)

class_delete_dialog.ClassDeleteDialog = _FakeDeleteDialog


def person(cid: int) -> LabelClass:
    return LabelClass(id=cid, name=f"person{cid}", color="#00ff00",
                      annotation_type="keypoints",
                      skeleton=[SkeletonKeypoint("head", [1]), SkeletonKeypoint("neck", [0, 2]),
                                SkeletonKeypoint("pelvis", [1])])

def box(cid: int, name: str = "") -> LabelClass:
    return LabelClass(id=cid, name=name or f"box{cid}", color="#ff0000", annotation_type="bbox")

def edges(c: LabelClass) -> list[tuple[int, int]]:
    return ClassSchemaEditorDialog._collect_edges(c.skeleton)

def open_editor(classes, row):
    dlg = ClassSchemaEditorDialog(classes, count_fn=lambda cid: 5)
    dlg._class_list.setCurrentRow(row)
    return dlg

def run(fn):
    try:
        fn()
        return True
    except Exception as e:                  # noqa: BLE001 — report any crash as FAIL
        print(f"      {type(e).__name__}: {e}")
        return False


# ═════════════════════════════════════════════════════════════════════════════
# §1  Delete the LAST class (regression: IndexError in _current_class)
# ═════════════════════════════════════════════════════════════════════════════
section("1. Delete the last class")

dlg = open_editor([box(0), box(1), box(2)], 2)
check("deleting the last class does not crash", run(dlg._delete_class))
check("two classes remain", [c.id for c in dlg._classes] == [0, 1])
check("the new last class is selected", dlg._class_list.currentRow() == 1
      and dlg._current_class() is dlg._classes[1])
check("deletion is queued for main_window", dlg.pending_deletions == [(2, None)])

dlg = open_editor([box(0), box(1)], 1)
check("delete last twice in a row: no crash",
      run(dlg._delete_class) and dlg._class_list.currentRow() == 0)

dlg = open_editor([box(0), box(1)], 0)
new = box(7, "fresh"); dlg._new_class_ids.add(7); dlg._classes.append(new)
dlg._refresh_list(); dlg._class_list.setCurrentRow(2)
check("deleting a just-added last class does not crash", run(dlg._delete_class))
check("just-added class removed without a pending deletion",
      [c.id for c in dlg._classes] == [0, 1] and dlg.pending_deletions == [])


# ═════════════════════════════════════════════════════════════════════════════
# §2  Delete a class in the middle — the next class must not get its form data
# ═════════════════════════════════════════════════════════════════════════════
section("2. Delete in the middle")

dlg = open_editor([box(0), box(1), person(2)], 1)
check("deleting a middle class does not crash", run(dlg._delete_class))
kp = dlg._classes[1]
check("the keypoints class that slid up keeps its skeleton edges",
      edges(kp) == [(0, 1), (1, 2)])
check("it is now selected and shown", dlg._current_class() is kp
      and dlg._edges_edit.text() == "0-1, 1-2")


# ═════════════════════════════════════════════════════════════════════════════
# §3  Move up / down — edges typed in the form go to the right class
# ═════════════════════════════════════════════════════════════════════════════
section("3. Move up / down")

a, b = person(0), person(1)
dlg = open_editor([a, b], 1)
dlg._edges_edit.setText("0-2")              # typed, not yet committed
dlg._move_up()
moved, other = dlg._classes[0], dlg._classes[1]
check("moved class is the one that was edited", moved.id == 1)
check("uncommitted edges saved into the moved class", edges(moved) == [(0, 2)])
check("the neighbour keeps its own edges", edges(other) == [(0, 1), (1, 2)])

dlg = open_editor([person(0), person(1)], 0)
dlg._edges_edit.setText("1-2")
dlg._move_down()
check("move down: edited class gets the edges",
      edges(dlg._classes[1]) == [(1, 2)] and dlg._classes[1].id == 0)
check("move down: neighbour untouched", edges(dlg._classes[0]) == [(0, 1), (1, 2)])


# ═════════════════════════════════════════════════════════════════════════════
# §4  Cancel in the delete dialog keeps the editor working
# ═════════════════════════════════════════════════════════════════════════════
section("4. Cancelled delete")

_FakeDeleteDialog.accept = False
dlg = open_editor([box(0), person(1)], 1)
dlg._delete_class()
check("cancel keeps all classes", len(dlg._classes) == 2 and dlg.pending_deletions == [])
check("selection still active after cancel", dlg._current_class() is dlg._classes[1])
dlg._edges_edit.setText("0-2")
dlg._accept()                              # OK flushes the form
check("form edits still reach the class after cancel", edges(dlg.result_classes[1]) == [(0, 2)])
_FakeDeleteDialog.accept = True


# ═════════════════════════════════════════════════════════════════════════════
print(f"\n{'=' * 60}\n  {_pass} passed, {_fail} failed\n{'=' * 60}")
sys.exit(1 if _fail else 0)
