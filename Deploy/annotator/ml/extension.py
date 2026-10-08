"""
Entry point of the ML extension. The main window calls only:

    self._ml = install(self)       # in __init__, inside try/except
    self._ml.retranslate()         # on language change
    self._ml.shutdown()            # in closeEvent

It adds an "ML" menu (before Help) and a status-bar indicator; it needs
nothing else from the window but menuBar() and statusBar().
"""
from __future__ import annotations

from PyQt6.QtCore import QObject, QTimer
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import QMainWindow, QMenu, QToolButton

from annotator.ml import config
from annotator.ml.client import MLBackend
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
        self.backend = MLBackend(self)

        self._menu = QMenu(window)
        self._act_settings = QAction(window)
        self._act_settings.triggered.connect(self.open_settings)
        self._act_restart = QAction(window)
        self._act_restart.triggered.connect(self.backend.restart)
        self._act_stop = QAction(window)
        self._act_stop.triggered.connect(self.backend.stop)
        self._menu.addAction(self._act_settings)
        self._menu.addSeparator()
        self._menu.addAction(self._act_restart)
        self._menu.addAction(self._act_stop)
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

    # ── called by the main window ─────────────────────────────────────────────

    def retranslate(self) -> None:
        self._menu.setTitle(t("menu_ml"))
        self._act_settings.setText(t("act_settings"))
        self._act_restart.setText(t("act_restart"))
        self._act_stop.setText(t("act_stop"))
        self._on_state(self.backend.state)

    def shutdown(self) -> None:
        self.backend.stop()

    # ── UI ────────────────────────────────────────────────────────────────────

    def open_settings(self) -> None:
        from annotator.ml.settings_dialog import MLSettingsDialog
        MLSettingsDialog(self.backend, self._window).exec()
        self._on_state(self.backend.state)

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
