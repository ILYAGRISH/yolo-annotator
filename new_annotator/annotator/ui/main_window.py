"""
MainWindow — wires controller, scene, panels, toolbar, and keyboard shortcuts.
All annotation logic lives in the controller; window only routes signals.
"""
from pathlib import Path

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QAction, QKeySequence, QShortcut
from PyQt6.QtGui import QActionGroup
from PyQt6.QtWidgets import (QDialog, QFileDialog, QMainWindow, QMessageBox,
                              QSplitter, QStatusBar, QTabWidget, QToolBar,
                              QWidget, QVBoxLayout, QLabel)

from annotator.controller.project_controller import ProjectController
from annotator.domain.label_class import ANNOTATION_TYPE_DEFAULT_TOOL, ANNOTATION_TYPE_TOOLS
from annotator.tools.bbox_tool import BBoxTool
from annotator.tools.crack_tool import CrackTool
from annotator.tools.obb_tool import OBBTool
from annotator.tools.polygon_tool import PolygonTool, PolylineTool
from annotator.tools.pose_tool import PoseTool
from annotator.tools.select_tool import SelectTool
from annotator.ui.canvas.scene import AnnotationScene
from annotator.ui.canvas.view import AnnotationView
from annotator.ui.dialogs.class_delete_dialog import ClassDeleteDialog
from annotator.ui.dialogs.class_import_dialog import ClassImportDialog
from annotator.ui.dialogs.class_schema_editor import ClassSchemaEditorDialog
from annotator.ui.dialogs.export_dialog import ExportDatasetDialog
from annotator.ui.dialogs.new_project_dialog import NewProjectDialog
from annotator.ui.panels.annotations_panel import AnnotationsPanel
from annotator.ui.panels.classes_panel import ClassesPanel
from annotator.ui.panels.images_panel import ImagesPanel
from annotator.ui.panels.qc_panel import QCPanel
from annotator.ui.panels.tool_props_panel import ToolPropsPanel


class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Annotator  —  no project")
        self.resize(1400, 880)
        self._ctrl = ProjectController(self)
        self._tools = self._build_tools()
        self._plugin_tool_names: set[str] = set()
        self._setup_ui()
        self._setup_menu()
        self._setup_toolbar()
        self._setup_shortcuts()
        self._connect_signals()
        self._setup_autosave()
        self._load_plugins()
        self._activate_tool("select")

    # ── layout ────────────────────────────────────────────────────────────────

    def _setup_ui(self):
        self._scene = AnnotationScene()
        self._view = AnnotationView(self._scene)

        self._images_panel = ImagesPanel()
        self._classes_panel = ClassesPanel()
        self._annotations_panel = AnnotationsPanel()
        self._qc_panel = QCPanel()

        left = QSplitter(Qt.Orientation.Vertical)
        left.addWidget(self._images_panel)
        left.addWidget(self._classes_panel)
        left.setSizes([420, 200])

        self._right_tabs = QTabWidget()
        self._right_tabs.addTab(self._annotations_panel, "Annotations")
        self._right_tabs.addTab(self._qc_panel, "QC")

        self._tool_props = ToolPropsPanel()
        center = QWidget()
        center_layout = QVBoxLayout(center)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(0)
        center_layout.addWidget(self._tool_props)
        center_layout.addWidget(self._view)

        main = QSplitter(Qt.Orientation.Horizontal)
        main.addWidget(left)
        main.addWidget(center)
        main.addWidget(self._right_tabs)
        main.setSizes([230, 940, 230])
        self.setCentralWidget(main)

        self._status = QStatusBar()
        self.setStatusBar(self._status)
        self._status.showMessage("Ready  —  File › New Project to get started")

    # ── menus ─────────────────────────────────────────────────────────────────

    def _setup_menu(self):
        mb = self.menuBar()

        # File
        file_m = mb.addMenu("&File")
        self._add_action(file_m, "&New Project…",   self._new_project, "Ctrl+N")
        self._add_action(file_m, "&Open Project…",  self._open_project, "Ctrl+O")
        self._add_action(file_m, "&Save Project",   self._ctrl.save_project, "Ctrl+S")
        self._add_action(file_m, "&Close Project",  self._close_project)
        file_m.addSeparator()
        self._add_action(file_m, "Add Images from Folder…", self._add_images)
        file_m.addSeparator()
        self._add_action(file_m, "Export Dataset…", self._export_dataset, "Ctrl+E")
        file_m.addSeparator()
        self._add_action(file_m, "&Quit", self.close, "Ctrl+Q")

        # Edit
        edit_m = mb.addMenu("&Edit")
        undo_act = self._ctrl.undo_stack.createUndoAction(self, "Undo")
        undo_act.setShortcut(QKeySequence.StandardKey.Undo)
        redo_act = self._ctrl.undo_stack.createRedoAction(self, "Redo")
        redo_act.setShortcut(QKeySequence.StandardKey.Redo)
        edit_m.addAction(undo_act)
        edit_m.addAction(redo_act)

        # Tools
        self._tools_menu = mb.addMenu("&Tools")
        tools_m = self._tools_menu
        self._menu_tool_acts: dict[str, QAction] = {}
        self._menu_tool_acts["select"]   = self._add_action(tools_m, "Select  [V]",   lambda: self._activate_tool("select"),   "V")
        self._menu_tool_acts["polygon"]  = self._add_action(tools_m, "Polygon  [P]",  lambda: self._activate_tool("polygon"),  "P")
        self._menu_tool_acts["polyline"] = self._add_action(tools_m, "Polyline  [L]", lambda: self._activate_tool("polyline"), "L")
        self._menu_tool_acts["bbox"]     = self._add_action(tools_m, "BBox  [B]",     lambda: self._activate_tool("bbox"),     "B")
        self._menu_tool_acts["obb"]       = self._add_action(tools_m, "OBB  [O]",       lambda: self._activate_tool("obb"),       "O")
        self._menu_tool_acts["crack_tool"] = self._add_action(tools_m, "Crack  [C]",    lambda: self._activate_tool("crack_tool"), "C")
        self._menu_tool_acts["pose"]      = self._add_action(tools_m, "Pose  [K]",     lambda: self._activate_tool("pose"),      "K")

        # Export (populated in File menu via Ctrl+E, this menu kept as alias)
        mb.addMenu("&Export")

        # Schema
        schema_m = mb.addMenu("&Schema")
        self._add_action(schema_m, "Edit Class Schema…", self._open_schema_editor)
        schema_m.addSeparator()
        self._add_action(schema_m, "Export class_schema.json…", self._export_schema)
        self._add_action(schema_m, "Import class_schema.json…", self._import_schema)

        # QC
        qc_m = mb.addMenu("&QC")
        self._add_action(qc_m, "Validate Project", self._run_validation, "Ctrl+Shift+V")
        qc_m.addSeparator()
        self._add_action(qc_m, "Export Report (JSON)…",
                         lambda: self._export_report("json"))
        self._add_action(qc_m, "Export Report (CSV)…",
                         lambda: self._export_report("csv"))

        mb.addMenu("&Help")

    def _add_action(self, menu, text: str, slot, shortcut: str = "") -> QAction:
        act = QAction(text, self)
        if shortcut:
            act.setShortcut(QKeySequence(shortcut))
        act.triggered.connect(slot)
        menu.addAction(act)
        return act

    # ── toolbar ───────────────────────────────────────────────────────────────

    def _setup_toolbar(self):
        tb = QToolBar("Tools")
        tb.setMovable(False)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, tb)

        grp = QActionGroup(self)
        grp.setExclusive(True)

        def _tool_action(icon_text: str, tool_name: str, shortcut: str) -> QAction:
            act = QAction(icon_text, self)
            act.setCheckable(True)
            act.setShortcut(QKeySequence(shortcut))
            act.triggered.connect(lambda: self._activate_tool(tool_name))
            grp.addAction(act)
            tb.addAction(act)
            return act

        self._act_select     = _tool_action("✦ Select",   "select",     "V")
        self._act_polygon    = _tool_action("⬠ Polygon",  "polygon",    "P")
        self._act_polyline   = _tool_action("〜 Polyline", "polyline",   "L")
        self._act_bbox       = _tool_action("▭ BBox",     "bbox",       "B")
        self._act_obb        = _tool_action("⬡ OBB",      "obb",        "O")
        self._act_crack      = _tool_action("⌇ Crack",    "crack_tool", "C")
        self._act_pose       = _tool_action("✿ Pose",     "pose",       "K")

        tb.addSeparator()
        act_fit = QAction("⊞ Fit  [F]", self)
        act_fit.triggered.connect(self._view.fit_scene)
        tb.addAction(act_fit)

        tb.addSeparator()
        hint = QLabel(
            "  Polygon/Polyline/Crack/Pose: click=add · RMB=undo · dbl-click or Enter=finish · Esc=cancel   "
            "BBox/OBB: drag   Select: click=pick · drag handle=move vertex · Del=delete   "
            "Wheel=zoom · MMB=pan   A/D=prev/next")
        hint.setStyleSheet("color:#777;font-size:11px;")
        tb.addWidget(hint)

        self._tool_act_map = {
            "select":     self._act_select,
            "polygon":    self._act_polygon,
            "polyline":   self._act_polyline,
            "bbox":       self._act_bbox,
            "obb":        self._act_obb,
            "crack_tool": self._act_crack,
            "pose":       self._act_pose,
        }

    # ── shortcuts ─────────────────────────────────────────────────────────────

    def _setup_shortcuts(self):
        QShortcut(QKeySequence("F"), self, self._view.fit_scene)
        QShortcut(QKeySequence("D"), self, self._images_panel.select_next)
        QShortcut(QKeySequence("A"), self, self._images_panel.select_prev)
        QShortcut(QKeySequence("Escape"), self,
                  lambda: self._active_tool_obj().on_key_press(
                      Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier))
        QShortcut(QKeySequence("Delete"), self,
                  lambda: self._active_tool_obj().on_key_press(
                      Qt.Key.Key_Delete, Qt.KeyboardModifier.NoModifier))

    # ── signal wiring ─────────────────────────────────────────────────────────

    def _connect_signals(self):
        self._ctrl.project_changed.connect(self._on_project_changed)
        self._ctrl.image_changed.connect(self._on_image_changed)
        self._ctrl.annotations_changed.connect(self._on_annotations_changed)
        self._ctrl.annotation_selected.connect(self._on_annotation_selected)
        self._ctrl.status_message.connect(self._status.showMessage)

        self._images_panel.image_selected.connect(self._ctrl.set_image)
        self._images_panel.split_changed.connect(self._ctrl.save_project)
        self._classes_panel.class_selected.connect(self._on_class_selected)
        self._classes_panel.open_schema_editor.connect(self._open_schema_editor)
        self._annotations_panel.select_requested.connect(self._on_ann_panel_select)
        self._annotations_panel.delete_requested.connect(self._ctrl.delete_annotation)
        self._annotations_panel.edit_source_requested.connect(
            self._on_edit_crack_source)
        self._annotations_panel.classify_image_requested.connect(
            self._on_classify_image)
        self._qc_panel.validate_requested.connect(self._run_validation)
        self._qc_panel.navigate_requested.connect(self._on_qc_navigate)
        self._tool_props.params_changed.connect(self._on_tool_params_changed)

    # ── autosave ──────────────────────────────────────────────────────────────

    def _setup_autosave(self):
        self._autosave_timer = QTimer(self)
        self._autosave_timer.timeout.connect(self._ctrl.save_project)
        self._autosave_timer.start(60_000)

    # ── tool management ───────────────────────────────────────────────────────

    def _build_tools(self) -> dict:
        return {
            "select":     SelectTool(),
            "polygon":    PolygonTool(),
            "polyline":   PolylineTool(),
            "bbox":       BBoxTool(),
            "obb":        OBBTool(),
            "crack_tool": CrackTool(),
            "pose":       PoseTool(),
        }

    def _activate_tool(self, name: str):
        tool = self._tools.get(name)
        if tool is None:
            return
        self._scene.set_tool(tool, self._ctrl)
        cls = self._classes_panel.current_class_id
        if cls is not None and hasattr(tool, "set_class"):
            tool.set_class(cls)
        for tname, act in self._tool_act_map.items():
            act.setChecked(tname == name)
        from PyQt6.QtGui import QCursor
        self._view.setCursor(QCursor(tool.cursor))
        if hasattr(tool, "get_params_schema"):
            self._tool_props.load_tool(tool)
        else:
            self._tool_props.clear_tool()

    def _active_tool_obj(self):
        return self._scene.active_tool

    def _on_tool_params_changed(self, params: dict):
        tool = self._scene.active_tool
        if hasattr(tool, "set_params"):
            tool.set_params(params)

    # ── controller signal handlers ────────────────────────────────────────────

    def _on_project_changed(self, project):
        self._images_panel.load_project(project)
        self._classes_panel.load_project(project)
        self._annotations_panel.load_project(project)
        self._annotations_panel.refresh([])
        self._annotations_panel.set_active_class(None)
        self._qc_panel.set_project_loaded(project is not None)
        if project is not None:
            self.setWindowTitle(f"Annotator  —  {project.name}")
            self._status.showMessage(
                f"{project.name}  ·  {len(project.images)} images  "
                f"·  {len(project.classes)} classes")
        else:
            self.setWindowTitle("Annotator  —  no project")
            self._scene.clear_image()
            self._status.showMessage("Ready  —  File › New Project to get started")

    def _on_image_changed(self, path: str, annotations: list):
        self._scene.load_image(path)
        self._scene.rebuild_annotations(annotations, self._ctrl.project)
        self._view.fit_scene()
        name = Path(path).name
        self._status.showMessage(f"{name}  ·  {len(annotations)} annotations")

    def _on_annotations_changed(self, annotations: list):
        self._scene.rebuild_annotations(annotations, self._ctrl.project)
        self._annotations_panel.refresh(annotations)
        if self._ctrl.current_image and annotations:
            self._images_panel.mark_annotated(self._ctrl.current_image)

    def _on_annotation_selected(self, ann_id: str):
        if ann_id:
            self._scene.select_by_id(ann_id)
            self._annotations_panel.set_selected(ann_id)
        else:
            self._scene.deselect_all()
            self._annotations_panel.set_selected("")

    def _on_class_selected(self, class_id: int):
        tool = self._scene.active_tool
        if hasattr(tool, "set_class"):
            tool.set_class(class_id)
        lc = None
        if self._ctrl.project:
            lc = next((c for c in self._ctrl.project.classes if c.id == class_id), None)
        self._enforce_class_tool(lc)
        # Reload skeleton in PoseTool whenever the class changes (skeleton may differ)
        pose = self._tools.get("pose")
        if pose is not None and hasattr(pose, "_load_skeleton"):
            pose._load_skeleton()
        # Notify annotations panel (for Classify button visibility)
        self._annotations_panel.set_active_class(lc)

    def _current_tool_name(self) -> str | None:
        active = self._scene.active_tool
        for name, tool in self._tools.items():
            if tool is active:
                return name
        return None

    def _enforce_class_tool(self, lc):
        """Auto-switch tool and enable/disable toolbar buttons based on class annotation_type."""
        compatible: list[str] = ANNOTATION_TYPE_TOOLS.get(lc.annotation_type, []) if lc else []

        if lc is not None:
            if lc.annotation_type == "classification":
                # Image-level labels have no drawing tool — always switch to Select
                if self._current_tool_name() != "select":
                    self._activate_tool("select")
            else:
                default_tool = ANNOTATION_TYPE_DEFAULT_TOOL.get(lc.annotation_type)
                cur = self._current_tool_name()
                if default_tool and cur != "select" and cur not in compatible:
                    self._activate_tool(default_tool)

        for tool_name, act in self._tool_act_map.items():
            if tool_name in self._plugin_tool_names:
                continue  # plugin tools are not filtered by class type
            act.setEnabled(tool_name == "select" or lc is None or tool_name in compatible)
        for tool_name, act in self._menu_tool_acts.items():
            if tool_name in self._plugin_tool_names:
                continue
            act.setEnabled(tool_name == "select" or lc is None or tool_name in compatible)

    def _on_ann_panel_select(self, ann_id: str):
        self._ctrl.select_annotation(ann_id)

    def _on_classify_image(self, class_id: int):
        if not self._ctrl.current_image:
            return
        from annotator.domain.annotation import Annotation, AnnotationType
        # Prevent duplicate label for the same class on this image
        for ann in self._ctrl.current_annotations:
            if ann.ann_type == AnnotationType.CLASSIFY and ann.class_id == class_id:
                cls = (self._ctrl.project.get_class(class_id)
                       if self._ctrl.project else None)
                name = cls.name if cls else str(class_id)
                QMessageBox.information(
                    self, "Already labeled",
                    f'This image is already labeled as "{name}".')
                return
        ann = Annotation.new(class_id, AnnotationType.CLASSIFY, {})
        self._ctrl.add_annotation(ann)

    def _on_edit_crack_source(self, ann_id: str):
        ann = self._ctrl.get_annotation(ann_id)
        if ann is None or "source_geometry" not in ann.data:
            return
        self._activate_tool("crack_tool")
        crack = self._tools.get("crack_tool")
        if crack is not None and hasattr(crack, "start_edit"):
            crack.start_edit(ann)

    # ── plugin loader ─────────────────────────────────────────────────────────

    def _load_plugins(self):
        from annotator.plugins.loader import load_plugins
        plugins_dir = Path(__file__).resolve().parent.parent.parent / "plugins"
        plugin_tools = load_plugins(plugins_dir)
        if not plugin_tools:
            return
        self._tools_menu.addSeparator()
        for tool in plugin_tools:
            if tool.name in self._tools:
                continue
            self._tools[tool.name] = tool
            self._plugin_tool_names.add(tool.name)
            act = self._add_action(
                self._tools_menu,
                f"Plugin: {tool.name}",
                lambda tn=tool.name: self._activate_tool(tn),
            )
            self._tool_act_map[tool.name] = act

    # ── schema actions ────────────────────────────────────────────────────────

    def _open_schema_editor(self):
        if not self._ctrl.project:
            QMessageBox.information(self, "No project",
                                    "Open or create a project first.")
            return
        dlg = ClassSchemaEditorDialog(self._ctrl.project.classes, self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        self._ctrl.project.classes = dlg.result_classes
        self._ctrl.save_project()
        self._ctrl.project_changed.emit(self._ctrl.project)

    def _export_schema(self):
        if not self._ctrl.project:
            QMessageBox.information(self, "No project",
                                    "Open or create a project first.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export class schema", "class_schema.json",
            "JSON files (*.json)")
        if path:
            self._ctrl.export_class_schema(Path(path))

    def _import_schema(self):
        if not self._ctrl.project:
            QMessageBox.information(self, "No project",
                                    "Open or create a project first.")
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Import class schema", "", "JSON files (*.json)")
        if not path:
            return
        try:
            report = self._ctrl.import_class_schema(Path(path))
        except Exception as e:
            QMessageBox.critical(self, "Import error", str(e))
            return

        has_conflicts = any(r["conflict_type"] is not None for r in report)
        if has_conflicts:
            dlg = ClassImportDialog(report, self._ctrl.project.classes, self)
            if dlg.exec() != QDialog.DialogCode.Accepted:
                return
            self._ctrl.apply_import_schema(dlg.resolved_classes, dlg.remap)
        else:
            # No conflicts — add all directly
            classes = [r["incoming"] for r in report]
            self._ctrl.apply_import_schema(classes, {})

    # ── QC actions ────────────────────────────────────────────────────────────

    def _run_validation(self):
        if not self._ctrl.project:
            QMessageBox.information(self, "No project",
                                    "Open or create a project first.")
            return
        try:
            report = self._ctrl.run_validation()
            self._qc_panel.show_report(report)
            self._right_tabs.setCurrentWidget(self._qc_panel)
            n = len(report.issues)
            self._status.showMessage(
                f"Validation complete  ·  {n} issue{'s' if n != 1 else ''}  "
                f"({report.error_count} errors, {report.warning_count} warnings)")
        except Exception as exc:
            QMessageBox.critical(self, "Validation error", str(exc))

    def _export_report(self, fmt: str):
        if not self._ctrl.project:
            QMessageBox.information(self, "No project",
                                    "Open or create a project first.")
            return
        ext = fmt
        path, _ = QFileDialog.getSaveFileName(
            self, f"Export validation report", f"report.{ext}",
            f"{ext.upper()} files (*.{ext})")
        if path:
            self._ctrl.export_validation_report(Path(path), fmt)

    def _on_qc_navigate(self, image_path: str, ann_id: str):
        self._ctrl.set_image(image_path)
        self._images_panel.select_by_path(image_path)
        if ann_id:
            self._ctrl.select_annotation(ann_id)

    # ── export dataset ────────────────────────────────────────────────────────

    def _export_dataset(self):
        if not self._ctrl.project:
            QMessageBox.information(self, "No project",
                                    "Open or create a project first.")
            return
        counts = self._ctrl.get_annotation_type_counts()
        dlg = ExportDatasetDialog(self._ctrl.project, counts, self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        mismatches = self._ctrl.get_type_mismatches()
        if mismatches:
            detail = "\n".join(f"  • {m}" for m in mismatches)
            ret = QMessageBox.warning(
                self, "Annotation type mismatch",
                "Some annotations do not match their class schema type:\n\n"
                f"{detail}\n\n"
                "Mismatched annotations may be skipped during export. Continue?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No)
            if ret != QMessageBox.StandardButton.Yes:
                return
        try:
            self._ctrl.export_dataset(
                Path(dlg.output_dir), dlg.format_name, dlg.copy_images)
        except Exception as exc:
            QMessageBox.critical(self, "Export error", str(exc))

    # ── file / project actions ────────────────────────────────────────────────

    def _new_project(self):
        dlg = NewProjectDialog(self)
        if dlg.exec() != dlg.DialogCode.Accepted:
            return
        try:
            self._ctrl.create_project(dlg.project_name, Path(dlg.project_dir))
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def _close_project(self):
        if not self._ctrl.project:
            return
        if self._ctrl.is_dirty:
            ret = QMessageBox.question(
                self, "Unsaved changes",
                "The project has unsaved changes. Save before closing?",
                QMessageBox.StandardButton.Save |
                QMessageBox.StandardButton.Discard |
                QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Save)
            if ret == QMessageBox.StandardButton.Cancel:
                return
            if ret == QMessageBox.StandardButton.Save:
                self._ctrl.save_project()
        self._ctrl.close_project()

    def _open_project(self):
        folder = QFileDialog.getExistingDirectory(self, "Open .annproj folder")
        if not folder:
            return
        path = Path(folder)
        if not (path / "project.json").exists():
            QMessageBox.warning(self, "Not a project",
                                "Selected folder is not a valid .annproj project.")
            return
        try:
            self._ctrl.open_project(path)
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def _add_images(self):
        if not self._ctrl.project:
            QMessageBox.information(self, "No project",
                                    "Open or create a project first.")
            return
        folder = QFileDialog.getExistingDirectory(self, "Select image folder")
        if folder:
            self._ctrl.add_images_from_folder(Path(folder))

    # ── close ─────────────────────────────────────────────────────────────────

    def closeEvent(self, event):
        self._ctrl.save_project()
        event.accept()
