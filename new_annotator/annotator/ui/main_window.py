"""
MainWindow — wires controller, scene, panels, toolbar, and keyboard shortcuts.
All annotation logic lives in the controller; window only routes signals.
"""
from pathlib import Path

from PyQt6.QtCore import QEvent, Qt, QTimer
from PyQt6.QtGui import QAction, QKeySequence, QShortcut
from PyQt6.QtGui import QActionGroup
from PyQt6.QtWidgets import (QDialog, QFileDialog, QMainWindow, QMessageBox,
                              QSplitter, QStatusBar, QTabWidget, QToolBar,
                              QWidget, QVBoxLayout, QLabel)

from annotator.controller.project_controller import ProjectController
from annotator.domain.label_class import ANNOTATION_TYPE_DEFAULT_TOOL, ANNOTATION_TYPE_TOOLS
from annotator.i18n import current_language, set_language, tr
from annotator.tools.bbox_tool import BBoxTool
from annotator.tools.crack_tool import CrackTool
from annotator.tools.obb_tool import OBBTool
from annotator.tools.polygon_tool import PolygonTool, PolylineTool
from annotator.tools.brush_tool import BrushTool
from annotator.tools.point_tool import PointTool
from annotator.tools.pose_tool import PoseTool
from annotator.tools.select_tool import SelectTool
from annotator.ui.canvas.scene import AnnotationScene
from annotator.ui.canvas.view import AnnotationView
from annotator.ui.dialogs.class_delete_dialog import ClassDeleteDialog
from annotator.ui.dialogs.class_import_dialog import ClassImportDialog
from annotator.ui.dialogs.class_schema_editor import ClassSchemaEditorDialog
from annotator.ui.dialogs.export_dialog import ExportDatasetDialog
from annotator.ui.dialogs.new_project_dialog import NewProjectDialog
from annotator.ui.dialogs.project_settings_dialog import ProjectSettingsDialog
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
        self._user_role: str = "leader"   # "leader" or "client"
        self._user_name: str = ""
        self._tr_items: list[tuple] = []   # [(setter_callable, key), ...]
        self._setup_ui()
        self._setup_menu()
        self._setup_toolbar()
        self._setup_shortcuts()
        self._connect_signals()
        self._setup_autosave()
        self._setup_class_hotkeys()
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
        self._right_tabs.addTab(self._annotations_panel, tr("tab_annotations"))
        self._right_tabs.addTab(self._qc_panel, tr("tab_qc"))

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

    # ── translation helpers ───────────────────────────────────────────────────

    def _tmenu(self, parent, key: str):
        """Create QMenu with translated title and register for retranslation."""
        m = parent.addMenu(tr(key))
        self._tr_items.append((m.setTitle, key))
        return m

    def _tact(self, menu, key: str, slot, shortcut: str = "") -> QAction:
        """Create QAction with translated text, connect, and register for retranslation."""
        act = QAction(tr(key), self)
        if shortcut:
            act.setShortcut(QKeySequence(shortcut))
        act.triggered.connect(slot)
        menu.addAction(act)
        self._tr_items.append((act.setText, key))
        return act

    # ── menus ─────────────────────────────────────────────────────────────────

    def _setup_menu(self):
        mb = self.menuBar()

        # File
        file_m = self._tmenu(mb, "menu_file")
        self._tact(file_m, "act_new_project",      self._new_project,            "Ctrl+N")
        self._tact(file_m, "act_open_project",     self._open_project,           "Ctrl+O")
        self._tact(file_m, "act_save_project",     self._ctrl.save_project,      "Ctrl+S")
        self._tact(file_m, "act_close_project",    self._close_project)
        self._tact(file_m, "act_project_settings", self._open_project_settings)
        self._tact(file_m, "act_your_name",        self._change_user_name)
        file_m.addSeparator()
        self._tact(file_m, "act_add_images",       self._add_images)
        self._tact(file_m, "act_split_dataset",    self._split_dataset)
        self._tact(file_m, "act_import_dataset",   self._import_dataset)
        self._assign_act = self._tact(file_m, "act_assign_images", self._open_assign_dialog)
        self._assign_act.setEnabled(False)
        file_m.addSeparator()
        self._tact(file_m, "act_export_dataset",   self._export_dataset,         "Ctrl+E")
        file_m.addSeparator()
        self._tact(file_m, "act_quit",             self.close,                   "Ctrl+Q")

        # Edit
        edit_m = self._tmenu(mb, "menu_edit")
        self._undo_act = self._ctrl.undo_stack.createUndoAction(self, "Undo")
        self._undo_act.setShortcut(QKeySequence.StandardKey.Undo)
        self._redo_act = self._ctrl.undo_stack.createRedoAction(self, "Redo")
        self._redo_act.setShortcuts([
            QKeySequence.StandardKey.Redo,        # Ctrl+Y
            QKeySequence("Ctrl+Shift+Z"),          # common alternative
        ])
        edit_m.addAction(self._undo_act)
        edit_m.addAction(self._redo_act)

        # Tools (short technical names — kept in English universally)
        self._tools_menu = mb.addMenu("&Tools")
        tools_m = self._tools_menu
        self._menu_tool_acts: dict[str, QAction] = {}
        self._menu_tool_acts["select"]     = self._add_action(tools_m, "Select  [V]",   lambda: self._activate_tool("select"))
        self._menu_tool_acts["polygon"]    = self._add_action(tools_m, "Polygon  [P]",  lambda: self._activate_tool("polygon"))
        self._menu_tool_acts["polyline"]   = self._add_action(tools_m, "Polyline  [L]", lambda: self._activate_tool("polyline"))
        self._menu_tool_acts["bbox"]       = self._add_action(tools_m, "BBox  [B]",     lambda: self._activate_tool("bbox"))
        self._menu_tool_acts["obb"]        = self._add_action(tools_m, "OBB  [O]",      lambda: self._activate_tool("obb"))
        self._menu_tool_acts["crack_tool"] = self._add_action(tools_m, "Crack  [C]",    lambda: self._activate_tool("crack_tool"))
        self._menu_tool_acts["pose"]       = self._add_action(tools_m, "Pose  [K]",     lambda: self._activate_tool("pose"))
        self._menu_tool_acts["point"]      = self._add_action(tools_m, "Point  [.]",    lambda: self._activate_tool("point"))
        self._menu_tool_acts["brush"]      = self._add_action(tools_m, "Brush  [M]",    lambda: self._activate_tool("brush"))

        # Export (alias, no retranslation needed)
        mb.addMenu("&Export")

        # Schema
        schema_m = self._tmenu(mb, "menu_schema")
        self._tact(schema_m, "act_edit_schema",   self._open_schema_editor)
        schema_m.addSeparator()
        self._tact(schema_m, "act_export_schema", self._export_schema)
        self._tact(schema_m, "act_import_schema", self._import_schema)

        # QC
        qc_m = self._tmenu(mb, "menu_qc")
        self._tact(qc_m, "act_validate",           self._run_validation, "Ctrl+Shift+V")
        qc_m.addSeparator()
        self._tact(qc_m, "act_export_report_json", lambda: self._export_report("json"))
        self._tact(qc_m, "act_export_report_csv",  lambda: self._export_report("csv"))

        # Help
        help_m = self._tmenu(mb, "menu_help")
        self._tact(help_m, "act_about", self._show_about)

        # Language submenu
        lang_m = help_m.addMenu("Language")
        self._act_lang_en = QAction("English", self)
        self._act_lang_en.setCheckable(True)
        self._act_lang_ru = QAction("Русский", self)
        self._act_lang_ru.setCheckable(True)
        lang_grp = QActionGroup(self)
        lang_grp.addAction(self._act_lang_en)
        lang_grp.addAction(self._act_lang_ru)
        self._act_lang_en.triggered.connect(lambda: self._set_language("EN"))
        self._act_lang_ru.triggered.connect(lambda: self._set_language("RU"))
        lang_m.addAction(self._act_lang_en)
        lang_m.addAction(self._act_lang_ru)
        self._act_lang_en.setChecked(current_language() == "EN")
        self._act_lang_ru.setChecked(current_language() == "RU")

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
        self._toolbar = tb
        tb.setStyleSheet(
            "QToolButton:checked { background: #2a5ca0; border: 2px solid #6699ee;"
            " border-radius: 3px; color: white; }"
        )

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
        self._act_point      = _tool_action("• Point",    "point",      ".")
        self._act_brush      = _tool_action("⬤ Brush",    "brush",      "M")

        tb.addSeparator()
        act_fit = QAction("⊞ Fit  [F]", self)
        act_fit.triggered.connect(self._view.fit_scene)
        tb.addAction(act_fit)

        tb.addSeparator()
        self._toolbar_hint = QLabel(tr("toolbar_hint"))
        self._toolbar_hint.setStyleSheet("color:#777;font-size:11px;")
        tb.addWidget(self._toolbar_hint)

        self._tool_act_map = {
            "select":     self._act_select,
            "polygon":    self._act_polygon,
            "polyline":   self._act_polyline,
            "bbox":       self._act_bbox,
            "obb":        self._act_obb,
            "crack_tool": self._act_crack,
            "pose":       self._act_pose,
            "point":      self._act_point,
            "brush":      self._act_brush,
        }

    # ── shortcuts ─────────────────────────────────────────────────────────────

    def _setup_shortcuts(self):
        self._sc_fit  = QShortcut(QKeySequence("F"), self, self._view.fit_scene)
        self._sc_next = QShortcut(QKeySequence("D"), self, self._images_panel.select_next)
        self._sc_prev = QShortcut(QKeySequence("A"), self, self._images_panel.select_prev)
        QShortcut(QKeySequence("Escape"), self,
                  lambda: self._active_tool_obj().on_key_press(
                      Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier))
        QShortcut(QKeySequence("Delete"), self,
                  lambda: self._active_tool_obj().on_key_press(
                      Qt.Key.Key_Delete, Qt.KeyboardModifier.NoModifier))

    def _set_language(self, lang: str):
        set_language(lang)
        self._act_lang_en.setChecked(lang == "EN")
        self._act_lang_ru.setChecked(lang == "RU")
        self.retranslate()

    def retranslate(self):
        """Update all translatable UI strings to the current language."""
        for setter, key in self._tr_items:
            setter(tr(key))
        self._toolbar_hint.setText(tr("toolbar_hint"))
        self._right_tabs.setTabText(0, tr("tab_annotations"))
        self._right_tabs.setTabText(1, tr("tab_qc"))
        self._images_panel.retranslate()
        self._classes_panel.retranslate()
        self._annotations_panel.retranslate()
        self._qc_panel.retranslate()

    def _apply_hotkeys(self, hk: dict):
        from annotator.domain.project import DEFAULT_HOTKEYS
        h = {**DEFAULT_HOTKEYS, **hk}
        self._sc_fit.setKey(QKeySequence(h.get("view_fit", "")))
        self._sc_next.setKey(QKeySequence(h.get("navigate_next", "")))
        self._sc_prev.setKey(QKeySequence(h.get("navigate_prev", "")))
        tool_map = {
            "tool_select":   "select",
            "tool_polygon":  "polygon",
            "tool_polyline": "polyline",
            "tool_bbox":     "bbox",
            "tool_obb":      "obb",
            "tool_crack":    "crack_tool",
            "tool_pose":     "pose",
            "tool_point":    "point",
            "tool_brush":    "brush",
        }
        for hk_key, tool_name in tool_map.items():
            act = self._tool_act_map.get(tool_name)
            if act:
                act.setShortcut(QKeySequence(h.get(hk_key, "")))

    # ── signal wiring ─────────────────────────────────────────────────────────

    def _connect_signals(self):
        self._ctrl.project_changed.connect(self._on_project_changed)
        self._ctrl.image_changed.connect(self._on_image_changed)
        self._ctrl.annotations_changed.connect(self._on_annotations_changed)
        self._ctrl.annotation_selected.connect(self._on_annotation_selected)
        self._ctrl.status_message.connect(self._status.showMessage)

        self._images_panel.image_selected.connect(self._ctrl.set_image)
        self._images_panel.split_changed.connect(self._ctrl.save_project)
        self._images_panel.files_dropped.connect(self._on_images_dropped)
        self._classes_panel.class_selected.connect(self._on_class_selected)
        self._classes_panel.open_schema_editor.connect(self._open_schema_editor)
        self._annotations_panel.select_requested.connect(self._on_ann_panel_select)
        self._annotations_panel.delete_requested.connect(self._ctrl.delete_annotation)
        self._annotations_panel.edit_source_requested.connect(
            self._on_edit_crack_source)
        self._annotations_panel.classify_image_requested.connect(
            self._on_classify_image)
        self._annotations_panel.attribute_changed.connect(
            lambda ann_id, data: self._ctrl.update_annotation_data(
                ann_id, data, "Edit attributes"))
        self._qc_panel.validate_requested.connect(self._run_validation)
        self._qc_panel.navigate_requested.connect(self._on_qc_navigate)
        self._tool_props.params_changed.connect(self._on_tool_params_changed)
        self._tool_props.commit_requested.connect(
            lambda: self._active_tool_obj().on_key_press(
                Qt.Key.Key_Return, Qt.KeyboardModifier.NoModifier))

    # ── autosave ──────────────────────────────────────────────────────────────

    def _setup_autosave(self):
        self._autosave_timer = QTimer(self)
        self._autosave_timer.timeout.connect(self._ctrl.save_project)
        self._autosave_timer.start(60_000)

    # ── class digit hotkeys ───────────────────────────────────────────────────

    def _setup_class_hotkeys(self):
        self._digit_buffer = ""
        self._digit_timer = QTimer(self)
        self._digit_timer.setSingleShot(True)
        self._digit_timer.timeout.connect(self._commit_digit_class)
        from PyQt6.QtWidgets import QApplication
        QApplication.instance().installEventFilter(self)

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.KeyPress:
            from PyQt6.QtWidgets import QAbstractSpinBox, QLineEdit, QTextEdit, QApplication
            fw = QApplication.focusWidget()
            if not isinstance(fw, (QLineEdit, QTextEdit, QAbstractSpinBox)):
                key = event.key()
                if Qt.Key.Key_0 <= key <= Qt.Key.Key_9:
                    self._on_digit_pressed(str(key - Qt.Key.Key_0))
                    return True  # событие потреблено
        return False

    def _on_digit_pressed(self, digit: str):
        self._digit_buffer += digit
        if len(self._digit_buffer) >= 2:
            self._commit_digit_class()
        else:
            self._digit_timer.start(600)

    def _commit_digit_class(self):
        self._digit_timer.stop()
        buf, self._digit_buffer = self._digit_buffer, ""
        if buf and self._ctrl.project:
            self._classes_panel.select_class_by_id(int(buf))

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
            "point":      PointTool(),
            "brush":      BrushTool(),
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
        self._assign_act.setEnabled(
            project is not None and self._user_role == "leader")
        if project is not None:
            self.setWindowTitle(f"Annotator  —  {project.name}")
            self._status.showMessage(
                f"{project.name}  ·  {len(project.images)} images  "
                f"·  {len(project.classes)} classes")
            self._apply_hotkeys(project.settings.hotkeys)
        else:
            self.setWindowTitle("Annotator  —  no project")
            self._scene.clear_image()
            self._status.showMessage("Ready  —  File › New Project to get started")
            from annotator.domain.project import DEFAULT_HOTKEYS
            self._apply_hotkeys(DEFAULT_HOTKEYS)

    def _on_image_changed(self, path: str, annotations: list):
        self._scene.load_image(path)
        self._scene.rebuild_annotations(annotations, self._ctrl.project)
        self._view.fit_scene()
        name = Path(path).name
        self._status.showMessage(f"{name}  ·  {len(annotations)} annotations")

    def _on_annotations_changed(self, annotations: list):
        self._scene.rebuild_annotations(annotations, self._ctrl.project)
        self._annotations_panel.refresh(annotations)
        if self._ctrl.current_image:
            self._images_panel.set_annotated(self._ctrl.current_image, bool(annotations))

    def _on_annotation_selected(self, ann_id: str):
        if ann_id:
            self._scene.select_by_id(ann_id)
            self._annotations_panel.set_selected(ann_id)
            # After crack edit commits it calls select_annotation — switch back to Select
            crack = self._tools.get("crack_tool")
            if (self._current_tool_name() == "crack_tool"
                    and crack is not None
                    and not crack.is_editing):
                self._activate_tool("select")
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

        _HIGHLIGHT = (
            "QToolButton { background: rgba(80,180,80,45);"
            " border: 1px solid #4a8a4a; border-radius: 3px; }"
            " QToolButton:checked { background: #2a5ca0;"
            " border: 2px solid #6699ee; border-radius: 3px; color: white; }"
        )
        for tool_name, act in self._tool_act_map.items():
            if tool_name in self._plugin_tool_names:
                continue  # plugin tools are not filtered by class type
            act.setEnabled(tool_name == "select" or lc is None or tool_name in compatible)
            btn = self._toolbar.widgetForAction(act)
            if btn:
                highlight = (lc is not None and tool_name != "select"
                             and tool_name in compatible)
                btn.setStyleSheet(_HIGHLIGHT if highlight else "")
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
            # Reload panel so it reflects this annotation's stored buffer params
            self._tool_props.load_tool(crack)

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
        dlg = ClassSchemaEditorDialog(
            self._ctrl.project.classes, self,
            count_fn=self._ctrl.count_annotations_for_class)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        self._ctrl.project.classes = dlg.result_classes
        for class_id, reassign_to in dlg.pending_deletions:
            self._ctrl.delete_class(class_id, reassign_to)
        if not dlg.pending_deletions:
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

    # ── Help ─────────────────────────────────────────────────────────────────

    def _show_about(self):
        QMessageBox.about(
            self, "About YOLO Annotator",
            "<h3>YOLO Annotator</h3>"
            "<p><b>Version:</b> 1.3</p>"
            "<p><b>Author:</b> Ilya Grishutin</p>"
            "<p>Desktop image annotation tool for preparing<br>"
            "training datasets for computer vision tasks.</p>"
            "<p><a href='https://github.com/ILYAGRISH/yolo-annotator'>"
            "github.com/ILYAGRISH/yolo-annotator</a></p>"
        )

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
            if dlg.is_multitask:
                self._ctrl.export_multitask(
                    Path(dlg.output_dir), dlg.export_jobs, dlg.copy_images)
            else:
                self._ctrl.export_dataset(
                    Path(dlg.output_dir), dlg.format_name, dlg.copy_images)
        except Exception as exc:
            QMessageBox.critical(self, "Export error", str(exc))

    # ── multi-user (Variant A) ────────────────────────────────────────────────

    def _apply_multiuser_role(self):
        """Called after project is open. Determines leader vs client role."""
        import socket
        from annotator.storage.project_store import ProjectStore

        project = self._ctrl.project
        if project is None:
            return

        hostname = socket.gethostname()

        if not project.leader_machine:
            # First opener — claim leadership
            project.leader_machine = hostname
            self._ctrl.save_project()
            self._user_role = "leader"
            self._user_name = self._leader_display_name(hostname)
        elif project.leader_machine == hostname:
            self._user_role = "leader"
            self._user_name = self._leader_display_name(hostname)
        else:
            # Client — ask for name
            name = self._ask_user_name()
            if not name:
                self._ctrl.close_project()
                return

            path = project.project_path
            assignments = ProjectStore.load_assignments(path)
            users = assignments.get("users", {})

            if name not in users:
                QMessageBox.warning(
                    self, "Not assigned",
                    f'No images are assigned to "{name}".\n'
                    "Contact the project leader to assign images to you.")
                self._ctrl.close_project()
                return

            self._user_role = "client"
            self._user_name = name
            stems = set(users[name])
            self._images_panel.set_user_filter(stems)
            n = len(stems)
            self._status.showMessage(
                f"Opened as {name}  ·  {n} image{'s' if n != 1 else ''} assigned"
                + ("  ·  0 images — contact the leader" if n == 0 else ""))
            return

        # Leader path — load existing assignments to show in panel
        self._images_panel.set_user_filter(None)
        self._assign_act.setEnabled(True)
        path = project.project_path
        if path:
            assignments = ProjectStore.load_assignments(path)
            self._images_panel.set_assignments(assignments)

    def _ask_user_name(self) -> str:
        from PyQt6.QtCore import QSettings
        from PyQt6.QtWidgets import QInputDialog
        settings = QSettings("Annotator", "App")
        last = settings.value("user_name", "")
        name, ok = QInputDialog.getText(
            self, "Enter your name",
            "This project belongs to another computer.\n"
            "Enter your name to load your assigned images:",
            text=last)
        if ok and name.strip():
            settings.setValue("user_name", name.strip())
            return name.strip()
        return ""

    def _change_user_name(self):
        from PyQt6.QtCore import QSettings
        from PyQt6.QtWidgets import QInputDialog
        settings = QSettings("Annotator", "App")
        current = self._user_name or settings.value("user_name", "")
        name, ok = QInputDialog.getText(
            self, "Your name", "Enter your display name:", text=current)
        if not ok or not name.strip():
            return
        new_name = name.strip()
        old_name = self._user_name
        settings.setValue("user_name", new_name)
        self._user_name = new_name
        # If leader with open project — rename their entry in assignments.json
        if (self._user_role == "leader"
                and self._ctrl.project
                and self._ctrl.project.project_path
                and old_name and old_name != new_name):
            from annotator.storage.project_store import ProjectStore
            path = self._ctrl.project.project_path
            assignments = ProjectStore.load_assignments(path)
            users = assignments.get("users", {})
            if old_name in users:
                users[new_name] = users.pop(old_name)
                ProjectStore.save_assignments(path, assignments)
                self._images_panel.set_assignments(assignments)

    def _leader_display_name(self, hostname: str) -> str:
        """Return saved display name for leader. Asks once if not yet set."""
        from PyQt6.QtCore import QSettings
        from PyQt6.QtWidgets import QInputDialog
        settings = QSettings("Annotator", "App")
        saved = settings.value("user_name", "")
        if saved:
            return saved
        name, ok = QInputDialog.getText(
            self, "Your name",
            "Enter your name (used to identify you as the project leader):",
            text=hostname)
        name = name.strip() if (ok and name.strip()) else hostname
        settings.setValue("user_name", name)
        return name

    def _reset_multiuser(self):
        self._user_role = "leader"
        self._user_name = ""
        self._images_panel.set_user_filter(None)
        self._images_panel.set_assignments(None)
        self._assign_act.setEnabled(False)

    def _open_assign_dialog(self):
        if not self._ctrl.project or not self._ctrl.project.project_path:
            return
        from annotator.storage.project_store import ProjectStore
        from annotator.ui.dialogs.assign_images_dialog import AssignImagesDialog

        path = self._ctrl.project.project_path
        assignments = ProjectStore.load_assignments(path)
        dlg = AssignImagesDialog(
            self._ctrl.project.images, assignments,
            leader_name=self._user_name, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            result = dlg.result_assignments
            ProjectStore.save_assignments(path, result)
            self._images_panel.set_assignments(result)
            QMessageBox.information(
                self, "Assignments saved",
                "Assignments saved.\n"
                "Clients must reopen the project to see their updated image list.")

    # ── file / project actions ────────────────────────────────────────────────

    def _new_project(self):
        dlg = NewProjectDialog(self)
        if dlg.exec() != dlg.DialogCode.Accepted:
            return
        try:
            import socket
            self._ctrl.create_project(dlg.project_name, Path(dlg.project_dir))
            if self._ctrl.project:
                self._ctrl.project.leader_machine = socket.gethostname()
                self._ctrl.save_project()
            self._user_role = "leader"
            self._user_name = self._leader_display_name(socket.gethostname())
            self._images_panel.set_user_filter(None)
            self._images_panel.set_assignments(None)
            self._assign_act.setEnabled(True)
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
        self._reset_multiuser()

    def _open_project_settings(self):
        if not self._ctrl.project:
            QMessageBox.information(self, "No project",
                                    "Open or create a project first.")
            return
        dlg = ProjectSettingsDialog(self._ctrl.project, self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        name = dlg.project_name
        if not name:
            return
        settings = dlg.result_settings
        self._ctrl.update_project_settings(name, settings)
        # Apply new autosave interval and hotkeys immediately
        self._autosave_timer.setInterval(settings.autosave_interval_sec * 1000)
        self._apply_hotkeys(settings.hotkeys)

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
            self._reset_multiuser()
            self._ctrl.open_project(path)
            self._apply_multiuser_role()
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

    def _on_images_dropped(self, paths: list):
        if not self._ctrl.project:
            QMessageBox.information(self, "No project",
                                    "Open or create a project first.")
            return
        self._ctrl.add_images_from_paths(paths)

    def _split_dataset(self):
        if not self._ctrl.project:
            QMessageBox.information(self, "No project",
                                    "Open or create a project first.")
            return
        if not self._ctrl.project.images:
            QMessageBox.information(self, "No images",
                                    "Add images to the project first.")
            return
        from annotator.ui.dialogs.split_dataset_dialog import SplitDatasetDialog
        dlg = SplitDatasetDialog(self._ctrl.project, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._ctrl.split_dataset(
                dlg.val_pct, dlg.test_pct, dlg.mode, dlg.shuffle)

    def _import_dataset(self):
        if not self._ctrl.project:
            QMessageBox.information(self, "No project",
                                    "Open or create a project first.")
            return
        from annotator.ui.dialogs.import_dataset_dialog import ImportDatasetDialog
        dlg = ImportDatasetDialog(self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        if not dlg.dataset_folder or not dlg.class_names:
            return
        try:
            stats = self._ctrl.import_yolo_dataset(
                dlg.dataset_folder, dlg.class_names,
                dlg.ann_type, dlg.conflict_mode,
            )
        except Exception as exc:
            QMessageBox.critical(self, "Import error", str(exc))
            return

        warnings = stats.get("warnings", [])
        msg = (
            f"Import complete.\n\n"
            f"Images found:        {stats['images_found']}\n"
            f"Label files found:   {stats['labels_found']}\n"
            f"Annotations added:   {stats['annotations_added']}\n"
            f"Images skipped:      {stats['images_skipped']}\n"
            f"Classes created:     {stats['classes_created']}"
        )
        if warnings:
            msg += "\n\nWarnings:\n" + "\n".join(f"  • {w}" for w in warnings[:10])
            if len(warnings) > 10:
                msg += f"\n  … and {len(warnings) - 10} more"
        QMessageBox.information(self, "Import complete", msg)

    # ── close ─────────────────────────────────────────────────────────────────

    def closeEvent(self, event):
        self._ctrl.save_project()
        event.accept()
