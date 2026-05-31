from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QKeySequence, QShortcut
from PyQt6.QtWidgets import (QMainWindow, QSplitter, QStatusBar, QToolBar,
                              QVBoxLayout, QWidget)

from app.canvas.canvas_scene import AnnotationScene, ToolMode
from app.canvas.canvas_view import AnnotationView
from app.io.yolo_format import load_labels, save_labels
from app.panels.annotation_panel import AnnotationPanel
from app.panels.class_panel import ClassPanel
from app.panels.file_panel import FilePanel


class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("YOLO Labeler")
        self.resize(1280, 820)
        self._current_image: Path | None = None
        self._unsaved = False
        self._setup_ui()
        self._setup_toolbar()
        self._setup_shortcuts()
        self._connect_signals()

    # ── layout ───────────────────────────────────────────────────────────────

    def _setup_ui(self):
        self._scene = AnnotationScene()
        self._view = AnnotationView(self._scene)

        self._file_panel = FilePanel()
        self._class_panel = ClassPanel()
        self._ann_panel = AnnotationPanel()

        left = QSplitter(Qt.Orientation.Vertical)
        left.addWidget(self._file_panel)
        left.addWidget(self._class_panel)
        left.setSizes([350, 200])

        right_widget = QWidget()
        rl = QVBoxLayout(right_widget)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.addWidget(self._ann_panel)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(left)
        splitter.addWidget(self._view)
        splitter.addWidget(right_widget)
        splitter.setSizes([210, 860, 210])

        self.setCentralWidget(splitter)
        self._status = QStatusBar()
        self.setStatusBar(self._status)

    def _setup_toolbar(self):
        tb = QToolBar("Tools")
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, tb)

        self._act_select = QAction("✦ Select  [V]", self)
        self._act_select.setCheckable(True)
        self._act_select.setChecked(True)
        self._act_select.triggered.connect(lambda: self._set_tool(ToolMode.SELECT))

        self._act_polygon = QAction("⬠ Polygon  [P]", self)
        self._act_polygon.setCheckable(True)
        self._act_polygon.triggered.connect(lambda: self._set_tool(ToolMode.POLYGON))

        act_save = QAction("💾 Save  [Ctrl+S]", self)
        act_save.triggered.connect(self._save)

        act_fit = QAction("⊞ Fit  [F]", self)
        act_fit.triggered.connect(self._view.fit_image)

        for act in (self._act_select, self._act_polygon, act_save, act_fit):
            tb.addAction(act)

        self._tool_acts = [self._act_select, self._act_polygon]

        tb.addSeparator()
        tb.addWidget(self._make_hint_label())

    def _make_hint_label(self):
        from PyQt6.QtWidgets import QLabel
        lbl = QLabel("  Polygon: click=add pt · RMB=undo pt · dbl-click / click 1st pt=close · Esc=cancel   "
                     "Select: click handle=move vertex · Del=delete   "
                     "Wheel=zoom · MMB drag=pan   A/D=prev/next image")
        lbl.setStyleSheet("color:#888;font-size:11px;")
        return lbl

    def _setup_shortcuts(self):
        QShortcut(QKeySequence("V"), self, lambda: self._set_tool(ToolMode.SELECT))
        QShortcut(QKeySequence("P"), self, lambda: self._set_tool(ToolMode.POLYGON))
        QShortcut(QKeySequence("Ctrl+S"), self, self._save)
        QShortcut(QKeySequence("F"), self, self._view.fit_image)
        QShortcut(QKeySequence("D"), self, self._file_panel.select_next)
        QShortcut(QKeySequence("A"), self, self._file_panel.select_prev)
        QShortcut(QKeySequence(Qt.Key.Key_Delete), self, self._scene.delete_selected)
        QShortcut(QKeySequence(Qt.Key.Key_Escape), self, self._on_escape)

    def _connect_signals(self):
        self._file_panel.image_selected.connect(self._load_image)
        self._class_panel.class_selected.connect(self._on_class_changed)
        self._scene.annotations_changed.connect(self._on_annotations_changed)
        self._scene.annotation_selected.connect(self._ann_panel.set_selected)
        self._scene.selectionChanged.connect(self._on_scene_selection_changed)
        self._ann_panel.select_requested.connect(self._select_annotation)
        self._ann_panel.delete_requested.connect(self._delete_annotation)

    # ── tool management ───────────────────────────────────────────────────────

    def _set_tool(self, mode: ToolMode):
        self._scene.set_mode(mode)
        for act in self._tool_acts:
            act.setChecked(False)
        if mode == ToolMode.SELECT:
            self._act_select.setChecked(True)
            self._view.setCursor(Qt.CursorShape.ArrowCursor)
        elif mode == ToolMode.POLYGON:
            self._act_polygon.setChecked(True)
            self._view.setCursor(Qt.CursorShape.CrossCursor)

    def _on_escape(self):
        if self._scene.mode == ToolMode.POLYGON:
            self._scene.cancel_current_polygon()
        else:
            self._scene.clearSelection()

    # ── file / IO ─────────────────────────────────────────────────────────────

    def _get_label_path(self, image_path: Path) -> Path:
        return self._file_panel.label_folder / (image_path.stem + ".txt")

    def _load_image(self, path: str):
        if self._unsaved:
            self._save()
        self._current_image = Path(path)
        if not self._scene.load_image(path):
            self._status.showMessage(f"Failed to load: {path}")
            return

        self._scene.set_classes(self._class_panel.classes)
        label_path = self._get_label_path(self._current_image)
        annotations = load_labels(label_path)

        # Auto-add classes found in labels that aren't in the panel yet
        for ann in annotations:
            if not self._class_panel.get_by_id(ann.class_id):
                from app.panels.class_panel import _PALETTE
                color = _PALETTE[ann.class_id % len(_PALETTE)]
                self._class_panel._add(f"class_{ann.class_id}", color)

        self._scene.set_classes(self._class_panel.classes)
        self._scene.load_annotations(annotations)
        self._view.fit_image()
        self._unsaved = False
        self._refresh_ann_panel()
        self._status.showMessage(
            f"{self._current_image.name}  ·  {len(annotations)} annotations  ·  "
            f"{self._current_image.parent}")

    def _save(self):
        if not self._current_image:
            return
        label_path = self._get_label_path(self._current_image)
        save_labels(label_path, self._scene.save_annotations())
        self._unsaved = False
        self._file_panel.mark_labeled(str(self._current_image))
        self._status.showMessage(f"Saved → {label_path}")

    # ── annotation management ─────────────────────────────────────────────────

    def _on_class_changed(self, class_id: int):
        self._scene.set_current_class(class_id)

    def _on_annotations_changed(self):
        self._unsaved = True
        self._refresh_ann_panel()

    def _refresh_ann_panel(self):
        self._ann_panel.refresh(self._scene.annotations, self._class_panel.classes)

    def _on_scene_selection_changed(self):
        sel = self._scene.selectedItems()
        if sel and sel[0] in self._scene._items:
            self._ann_panel.set_selected(self._scene._items.index(sel[0]))
        else:
            self._ann_panel.set_selected(-1)

    def _select_annotation(self, index: int):
        if 0 <= index < len(self._scene._items):
            self._scene.clearSelection()
            self._scene._items[index].setSelected(True)

    def _delete_annotation(self, index: int):
        if 0 <= index < len(self._scene._items):
            self._scene.clearSelection()
            self._scene._items[index].setSelected(True)
            self._scene.delete_selected()

    def closeEvent(self, event):
        if self._unsaved:
            self._save()
        event.accept()
