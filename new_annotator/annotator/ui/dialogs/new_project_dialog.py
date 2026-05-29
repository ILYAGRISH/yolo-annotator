from pathlib import Path

from PyQt6.QtWidgets import (QDialog, QDialogButtonBox, QFileDialog,
                              QHBoxLayout, QLabel, QLineEdit,
                              QPushButton, QVBoxLayout)


class NewProjectDialog(QDialog):
    """Dialog to create a new project: name + location."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("New Project")
        self.setMinimumWidth(420)
        self.project_name = ""
        self.project_dir = ""

        lay = QVBoxLayout(self)

        lay.addWidget(QLabel("Project name:"))
        self._name = QLineEdit("untitled")
        lay.addWidget(self._name)

        lay.addWidget(QLabel("Save location:"))
        loc_row = QHBoxLayout()
        self._loc = QLineEdit()
        self._loc.setPlaceholderText("Choose folder…")
        btn_browse = QPushButton("Browse…")
        btn_browse.clicked.connect(self._browse)
        loc_row.addWidget(self._loc)
        loc_row.addWidget(btn_browse)
        lay.addLayout(loc_row)

        self._preview = QLabel()
        self._preview.setStyleSheet("color:#888;font-size:11px;")
        lay.addWidget(self._preview)
        self._name.textChanged.connect(self._update_preview)
        self._loc.textChanged.connect(self._update_preview)

        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                              QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self._ok)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

    def _browse(self):
        folder = QFileDialog.getExistingDirectory(self, "Select save location")
        if folder:
            self._loc.setText(folder)

    def _update_preview(self):
        name = self._name.text().strip()
        loc = self._loc.text().strip()
        if name and loc:
            self._preview.setText(f"→ {loc}\\{name}.annproj")
        else:
            self._preview.setText("")

    def _ok(self):
        name = self._name.text().strip()
        loc = self._loc.text().strip()
        if not name or not loc:
            return
        self.project_name = name
        self.project_dir = str(Path(loc) / f"{name}.annproj")
        self.accept()
