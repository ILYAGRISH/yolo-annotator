"""
AssignImagesDialog — leader UI for distributing images among annotators.

Layout:
  Left  — user list + Add / Remove buttons + Auto-distribute
  Right — selected user's images (top) + Unassigned pool (bottom)
           with Assign / Unassign buttons between them
"""
from __future__ import annotations

import random
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QDialogButtonBox, QHBoxLayout, QInputDialog,
    QLabel, QListWidget, QListWidgetItem, QMessageBox,
    QPushButton, QSplitter, QVBoxLayout, QWidget,
)

from annotator.domain.project import ImageRecord


class AssignImagesDialog(QDialog):

    def __init__(self, images: list[ImageRecord], assignments: dict,
                 leader_name: str = "", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Assign Images to Users")
        self.resize(820, 580)

        self._images = images
        self._leader_name = leader_name  # current leader display name
        # Internal model: {name: set of stems}
        self._users: dict[str, set[str]] = {
            name: set(stems)
            for name, stems in assignments.get("users", {}).items()
        }
        # Auto-add the leader as a user if not already present
        if leader_name and leader_name not in self._users:
            self._users[leader_name] = set()

        self._setup_ui()
        self._refresh_user_list()
        # Pre-select leader
        if leader_name:
            for i in range(self._user_list.count()):
                if self._user_list.item(i).data(Qt.ItemDataRole.UserRole) == leader_name:
                    self._user_list.setCurrentRow(i)
                    break
        self._refresh_unassigned()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _setup_ui(self):
        root = QVBoxLayout(self)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # ── left: user management ──────────────────────────────────────────
        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)

        # "Your name" row — visible when dialog has a leader_name
        self._my_name_label = QLabel()
        self._my_name_label.setStyleSheet("color:#aaa; font-size:11px;")
        btn_change_name = QPushButton("Change name…")
        btn_change_name.setFixedHeight(22)
        btn_change_name.clicked.connect(self._change_leader_name)
        name_row = QHBoxLayout()
        name_row.addWidget(self._my_name_label)
        name_row.addWidget(btn_change_name)
        ll.addLayout(name_row)
        self._update_my_name_label()

        ll.addWidget(QLabel("Users:"))

        self._user_list = QListWidget()
        self._user_list.currentRowChanged.connect(self._on_user_selected)
        ll.addWidget(self._user_list)

        btn_row = QHBoxLayout()
        btn_add = QPushButton("+ Add")
        btn_add.clicked.connect(self._add_user)
        btn_del = QPushButton("− Remove")
        btn_del.clicked.connect(self._remove_user)
        btn_row.addWidget(btn_add)
        btn_row.addWidget(btn_del)
        ll.addLayout(btn_row)

        btn_auto = QPushButton("Auto-distribute evenly")
        btn_auto.setToolTip(
            "Distribute all unassigned images evenly among existing users")
        btn_auto.clicked.connect(self._auto_distribute)
        ll.addWidget(btn_auto)

        splitter.addWidget(left)

        # ── right: image lists ─────────────────────────────────────────────
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)

        self._user_images_label = QLabel("Select a user to see their images")
        rl.addWidget(self._user_images_label)
        self._user_images_list = QListWidget()
        self._user_images_list.setSelectionMode(
            QListWidget.SelectionMode.ExtendedSelection)
        rl.addWidget(self._user_images_list)

        btn_unassign = QPushButton("↑  Unassign selected  (remove from user)")
        btn_unassign.clicked.connect(self._unassign_selected)
        rl.addWidget(btn_unassign)

        self._unassigned_label = QLabel("Unassigned:")
        rl.addWidget(self._unassigned_label)
        self._unassigned_list = QListWidget()
        self._unassigned_list.setSelectionMode(
            QListWidget.SelectionMode.ExtendedSelection)
        rl.addWidget(self._unassigned_list)

        btn_assign = QPushButton("↓  Assign selected to user")
        btn_assign.clicked.connect(self._assign_selected)
        rl.addWidget(btn_assign)

        splitter.addWidget(right)
        splitter.setSizes([240, 580])
        root.addWidget(splitter)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        root.addWidget(btns)

    # ── helpers ───────────────────────────────────────────────────────────────

    def _stem_to_name(self) -> dict[str, str]:
        return {Path(r.path).stem: Path(r.path).name for r in self._images}

    def _assigned_stems(self) -> set[str]:
        out: set[str] = set()
        for stems in self._users.values():
            out |= stems
        return out

    def _unassigned_stems(self) -> list[str]:
        assigned = self._assigned_stems()
        return sorted(
            Path(r.path).stem for r in self._images
            if Path(r.path).stem not in assigned
        )

    def _current_user(self) -> str | None:
        row = self._user_list.currentRow()
        if row < 0:
            return None
        return self._user_list.item(row).data(Qt.ItemDataRole.UserRole)

    # ── refresh ───────────────────────────────────────────────────────────────

    def _refresh_user_list(self):
        prev = self._current_user()
        self._user_list.clear()
        for name, stems in self._users.items():
            item = QListWidgetItem(f"{name}  ({len(stems)} images)")
            item.setData(Qt.ItemDataRole.UserRole, name)
            self._user_list.addItem(item)
        # restore selection
        if prev:
            for i in range(self._user_list.count()):
                if self._user_list.item(i).data(Qt.ItemDataRole.UserRole) == prev:
                    self._user_list.setCurrentRow(i)
                    return

    def _refresh_user_images(self):
        self._user_images_list.clear()
        name = self._current_user()
        if name is None:
            self._user_images_label.setText("Select a user to see their images")
            return
        stems = self._users.get(name, set())
        self._user_images_label.setText(f"{name}  —  {len(stems)} images")
        stem_to_name = self._stem_to_name()
        for stem in sorted(stems):
            fname = stem_to_name.get(stem, stem)
            item = QListWidgetItem(fname)
            item.setData(Qt.ItemDataRole.UserRole, stem)
            self._user_images_list.addItem(item)

    def _refresh_unassigned(self):
        self._unassigned_list.clear()
        unassigned = self._unassigned_stems()
        self._unassigned_label.setText(f"Unassigned  ({len(unassigned)}):")
        stem_to_name = self._stem_to_name()
        for stem in unassigned:
            fname = stem_to_name.get(stem, stem)
            item = QListWidgetItem(fname)
            item.setData(Qt.ItemDataRole.UserRole, stem)
            self._unassigned_list.addItem(item)

    def _full_refresh(self):
        self._refresh_user_list()
        self._refresh_user_images()
        self._refresh_unassigned()

    # ── actions ───────────────────────────────────────────────────────────────

    def _update_my_name_label(self):
        if self._leader_name:
            self._my_name_label.setText(f"You: {self._leader_name}")
        else:
            self._my_name_label.setText("")

    def _change_leader_name(self):
        from PyQt6.QtCore import QSettings
        name, ok = QInputDialog.getText(
            self, "Change your name",
            "Enter your new display name:",
            text=self._leader_name)
        if not ok or not name.strip():
            return
        new_name = name.strip()
        if new_name == self._leader_name:
            return
        # Rename in users dict (keep their assigned images)
        if self._leader_name in self._users:
            stems = self._users.pop(self._leader_name)
            self._users[new_name] = stems
        elif new_name not in self._users:
            self._users[new_name] = set()
        self._leader_name = new_name
        QSettings("Annotator", "App").setValue("user_name", new_name)
        self._update_my_name_label()
        self._full_refresh()
        # Re-select new name
        for i in range(self._user_list.count()):
            if self._user_list.item(i).data(Qt.ItemDataRole.UserRole) == new_name:
                self._user_list.setCurrentRow(i)
                break

    def _on_user_selected(self, _row: int):
        self._refresh_user_images()

    def _add_user(self):
        name, ok = QInputDialog.getText(self, "Add user", "User name:")
        if not ok or not name.strip():
            return
        name = name.strip()
        if name in self._users:
            QMessageBox.warning(self, "Duplicate", f'User "{name}" already exists.')
            return
        self._users[name] = set()
        self._full_refresh()
        # select new user
        for i in range(self._user_list.count()):
            if self._user_list.item(i).data(Qt.ItemDataRole.UserRole) == name:
                self._user_list.setCurrentRow(i)
                break

    def _remove_user(self):
        name = self._current_user()
        if name is None:
            return
        stems = self._users.get(name, set())
        if stems:
            ret = QMessageBox.question(
                self, "Remove user",
                f'Remove "{name}"?\n'
                f'Their {len(stems)} image(s) will become unassigned.',
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if ret != QMessageBox.StandardButton.Yes:
                return
        del self._users[name]
        self._full_refresh()

    def _assign_selected(self):
        name = self._current_user()
        if name is None:
            QMessageBox.information(
                self, "No user selected",
                "Select a user from the left panel first.")
            return
        selected = self._unassigned_list.selectedItems()
        if not selected:
            return
        for item in selected:
            self._users[name].add(item.data(Qt.ItemDataRole.UserRole))
        self._full_refresh()

    def _unassign_selected(self):
        name = self._current_user()
        if name is None:
            return
        selected = self._user_images_list.selectedItems()
        if not selected:
            return
        for item in selected:
            self._users[name].discard(item.data(Qt.ItemDataRole.UserRole))
        self._full_refresh()

    def _auto_distribute(self):
        if not self._users:
            QMessageBox.information(
                self, "No users", "Add at least one user first.")
            return
        unassigned = self._unassigned_stems()
        if not unassigned:
            QMessageBox.information(
                self, "Nothing to distribute",
                "All images are already assigned.")
            return
        random.shuffle(unassigned)
        users = list(self._users.keys())
        for i, stem in enumerate(unassigned):
            self._users[users[i % len(users)]].add(stem)
        self._full_refresh()

    # ── result ────────────────────────────────────────────────────────────────

    @property
    def result_assignments(self) -> dict:
        return {
            "version": 1,
            "users": {name: sorted(stems)
                      for name, stems in self._users.items()},
        }
