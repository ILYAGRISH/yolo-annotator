"""
Entry point of the ML extension. The main window calls only:

    self._ml = install(self)       # in __init__, inside try/except
    self._ml.retranslate()         # on language change
    self._ml.shutdown()            # in closeEvent

and offers it a small public surface: menuBar(), statusBar(), .controller
and .allowed_image_paths(). The extension adds an "ML" menu (before Help)
and a status-bar indicator.
"""
from __future__ import annotations

from PyQt6.QtCore import QObject, QTimer
from PyQt6.QtGui import QAction, QKeySequence
from PyQt6.QtWidgets import QMainWindow, QMenu, QMessageBox, QToolButton

from annotator.ml import config
from annotator.ml.client import MLBackend
from annotator.ml.convert import is_model_annotation
from annotator.ml.prelabel import PrelabelRunner, PrelabelSummary
from annotator.ml.prelabel_settings import EXISTING_REPLACE, EXISTING_SKIP, PrelabelSettings
from annotator.ml.strings import t

_STATE_COLORS = {
    MLBackend.STOPPED: "#888888",
    MLBackend.STARTING: "#d4a017",
    MLBackend.READY: "#3aa655",
    MLBackend.BUSY: "#e08a1e",
    MLBackend.ERROR: "#d9534f",
}


class MLExtension(QObject):

    def __init__(self, window: QMainWindow):
        super().__init__(window)
        self._window = window
        self._ctrl = window.controller
        self.backend = MLBackend(self)
        self.runner = PrelabelRunner(self.backend, self._ctrl, self)
        self._quick = False                       # the running job came from Ctrl+L
        self.runner.finished.connect(self._on_quick_finished)

        self._menu = QMenu(window)
        self._act_image = self._action(self.prelabel_current_image, "Ctrl+L")
        self._act_dataset = self._action(self.open_prelabel, "Ctrl+Shift+L")
        self._act_remove = self._action(self.remove_model_annotations)
        self._act_settings = self._action(self.open_settings)
        self._act_restart = self._action(self.backend.restart)
        self._act_stop = self._action(self.backend.stop)
        for a in (self._act_image, self._act_dataset, self._act_remove, None,
                  self._act_settings, None, self._act_restart, self._act_stop):
            self._menu.addSeparator() if a is None else self._menu.addAction(a)
        self._menu.aboutToShow.connect(self._update_actions)
        mb = window.menuBar()
        actions = mb.actions()
        if actions:                                   # before Help (the last menu)
            mb.insertMenu(actions[-1], self._menu)
        else:
            mb.addMenu(self._menu)

        self._indicator = QToolButton()
        self._indicator.setAutoRaise(True)
        self._indicator.clicked.connect(self.open_settings)
        window.statusBar().addPermanentWidget(self._indicator)

        self.backend.state_changed.connect(self._on_state)
        self.retranslate()

        if config.autostart() and config.resolve_python() is not None:
            QTimer.singleShot(1000, self.backend.start)   # after the window is up

    def _action(self, slot, shortcut: str = "") -> QAction:
        act = QAction(self._window)
        act.triggered.connect(lambda _=False: slot())
        if shortcut:
            act.setShortcut(QKeySequence(shortcut))
        return act

    # ── called by the main window ─────────────────────────────────────────────

    def retranslate(self) -> None:
        self._menu.setTitle(t("menu_ml"))
        for act, key in ((self._act_image, "act_prelabel_image"),
                         (self._act_dataset, "act_prelabel_dataset"),
                         (self._act_remove, "act_remove_model"),
                         (self._act_settings, "act_settings"),
                         (self._act_restart, "act_restart"),
                         (self._act_stop, "act_stop")):
            act.setText(t(key))
        self._on_state(self.backend.state)

    def shutdown(self) -> None:
        self.runner.cancel()
        self.backend.stop()

    # ── pre-labelling ─────────────────────────────────────────────────────────

    def open_prelabel(self) -> None:
        if self._ctrl.project is None:
            self._status(t("pl_no_project"))
            return
        if self.runner.running:
            self._status(t("pl_quick_busy"))
            return
        from annotator.ml.prelabel_dialog import PrelabelDialog
        PrelabelDialog(self.backend, self.runner, self._ctrl,
                       self._window.allowed_image_paths, self._window).exec()

    def prelabel_current_image(self) -> None:
        """Ctrl+L: the current image with the saved model / mapping; replaces this
        image's earlier model annotations (one Ctrl+Z undoes it)."""
        project, path = self._ctrl.project, self._ctrl.current_image
        if project is None:
            self._status(t("pl_no_project"))
            return
        if not path:
            self._status(t("pl_no_image"))
            return
        if self.runner.running:
            self._status(t("pl_quick_busy"))
            return
        if path not in set(self._window.allowed_image_paths()):
            self._status(t("pl_not_allowed"))
            return
        settings = PrelabelSettings.load(project.project_path)
        ids = settings.mapping_for(settings.model) or {}
        mapping = {mid: project.get_class(cid) for mid, cid in ids.items() if cid is not None}
        mapping = {k: v for k, v in mapping.items() if v is not None}
        if not settings.model or not mapping:
            self.open_prelabel()                   # first use: choose model and classes
            return
        existing = EXISTING_REPLACE if settings.existing == EXISTING_SKIP else settings.existing
        self._quick = True
        self._status(t("loading"))
        self.runner.start([path], settings, mapping, existing)

    def _on_quick_finished(self, s: PrelabelSummary) -> None:
        if not self._quick:
            return
        self._quick = False
        if s.fatal:
            self._status(f"{t('error')}: {s.fatal}")
        elif s.failed:
            self._status(f"{t('error')}: {'; '.join(s.errors)}")
        else:
            settings = PrelabelSettings.load(self._ctrl.project.project_path)
            self._status(t("pl_quick_done", model=settings.model.replace("\\", "/").split("/")[-1],
                           n=s.added, sec=s.seconds))

    def remove_model_annotations(self) -> None:
        if self._ctrl.project is None:
            self._status(t("pl_no_project"))
            return
        current = self._ctrl.current_image
        per_image = {}
        for p in self._window.allowed_image_paths():
            ids = [a.id for a in self._ctrl.annotations_for(p) if is_model_annotation(a)]
            if ids:
                per_image[p] = ids
        total = sum(len(v) for v in per_image.values())
        if not total:
            QMessageBox.information(self._window, t("rm_title"), t("rm_none"))
            return
        cur_n = len(per_image.get(current, []))
        box = QMessageBox(QMessageBox.Icon.Question, t("rm_title"),
                          t("rm_text", cur=cur_n, all=total), parent=self._window)
        b_cur = box.addButton(t("rm_current"), QMessageBox.ButtonRole.AcceptRole)
        b_all = box.addButton(t("rm_all"), QMessageBox.ButtonRole.DestructiveRole)
        box.addButton(QMessageBox.StandardButton.Cancel)
        b_cur.setEnabled(cur_n > 0)
        box.exec()
        clicked = box.clickedButton()
        if clicked is b_cur:
            targets = {current: per_image[current]}
        elif clicked is b_all:
            targets = per_image
        else:
            return
        for p, ids in targets.items():
            self._ctrl.apply_annotation_changes(p, [], ids, text=t("act_remove_model"))
        if set(targets) - {current}:
            self._ctrl.project_changed.emit(self._ctrl.project)
        self._status(t("rm_done", n=sum(len(v) for v in targets.values())))

    # ── UI ────────────────────────────────────────────────────────────────────

    def open_settings(self) -> None:
        from annotator.ml.settings_dialog import MLSettingsDialog
        MLSettingsDialog(self.backend, self._window).exec()
        self._on_state(self.backend.state)

    def _update_actions(self) -> None:
        # the pre-label actions stay enabled: a disabled action would also block its
        # shortcut until the menu is opened again; their handlers explain what is missing
        self._act_stop.setEnabled(self.backend.running)

    def _status(self, text: str) -> None:
        self._window.statusBar().showMessage(text, 8000)

    def _on_state(self, state: str) -> None:
        self._indicator.setText(t(f"st_{state}"))
        self._indicator.setStyleSheet(
            f"QToolButton {{ color: {_STATE_COLORS.get(state, '#888')}; padding: 0 6px; }}")
        python = self.backend.python
        tip = t("st_tip", python=python if python else t("st_tip_none"))
        if state == MLBackend.ERROR and self.backend.last_error:
            tip += f"\n\n{self.backend.last_error}"
        self._indicator.setToolTip(tip)
        self._act_stop.setEnabled(self.backend.running)


def install(window: QMainWindow) -> MLExtension:
    return MLExtension(window)
