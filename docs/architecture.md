# Architecture — new_annotator

Version: 0.1 (Phase 0 baseline)  
Date: 2026-05-28

---

## 1. Goals

- Desktop annotation tool for computer vision datasets.
- Optimized for YOLO workflows; internal format is format-independent.
- Extensible via a plugin/tool API.
- Simple features run from a `.venv`; heavy ML isolated behind a separate backend.

---

## 2. Layer diagram

```
┌──────────────────────────────────────────────────────────┐
│                        UI Shell                          │
│   MainWindow · ToolBar · Dialogs · Menus                 │
└───────────────────────┬──────────────────────────────────┘
                        │  Qt signals / slots
┌───────────────────────▼──────────────────────────────────┐
│              Canvas / Interaction Layer                   │
│   AnnotationView(QGraphicsView)                          │
│   AnnotationScene(QGraphicsScene)                        │
│   Annotation item renderers (QGraphicsItem subclasses)   │
└───────────────────────┬──────────────────────────────────┘
                        │  BaseTool interface
┌───────────────────────▼──────────────────────────────────┐
│                    Tool System                            │
│   BaseTool ABC · SelectTool · PolygonTool                │
│   (Phase 6+) PluginTool · CrackTool                     │
└───────────────────────┬──────────────────────────────────┘
                        │  domain objects only
┌───────────────────────▼──────────────────────────────────┐
│               Project Domain Model                        │
│   Project · ImageRecord · LabelClass · Annotation        │
│   UndoStack (Phase 1)                                    │
└──────────┬────────────────────────────┬──────────────────┘
           │                            │
┌──────────▼──────────┐   ┌────────────▼─────────────────┐
│   Persistence Layer │   │   Import / Export Subsystem   │
│   ProjectStore      │   │   BaseExporter ABC            │
│   (JSON → Phase 1)  │   │   YoloExporter (Phase 5)     │
│   (SQLite → later)  │   │   CocoExporter (Phase 5)     │
└─────────────────────┘   └──────────────────────────────┘
                                        │
                           ┌────────────▼─────────────────┐
                           │    ML Backend (Phase 7+)      │
                           │   Subprocess / REST bridge    │
                           │   SAM · YOLO auto-label      │
                           └──────────────────────────────┘
```

---

## 3. Module layout

```
new_annotator/
├── main.py                      # entry point
├── requirements.txt             # base deps: PyQt6, Pillow
├── run.bat / install.bat
├── .venv/
└── annotator/
    ├── app.py                   # QApplication, dark palette, app init
    ├── ui/
    │   ├── main_window.py       # QMainWindow, toolbar, panel layout
    │   ├── canvas/
    │   │   ├── view.py          # AnnotationView (zoom/pan)
    │   │   ├── scene.py         # AnnotationScene (delegates to active tool)
    │   │   └── items/
    │   │       ├── base_item.py         # BaseAnnotationItem ABC
    │   │       ├── polygon_item.py      # polygon / segmentation
    │   │       ├── bbox_item.py         # (Phase 1)
    │   │       └── keypoint_item.py     # (Phase 3)
    │   ├── panels/
    │   │   ├── images_panel.py          # project image list
    │   │   ├── classes_panel.py         # class manager
    │   │   └── annotations_panel.py     # per-image annotation list
    │   └── dialogs/
    │       ├── new_project_dialog.py
    │       └── settings_dialog.py       # (Phase 2)
    ├── domain/
    │   ├── project.py           # Project, ProjectSettings, ImageRecord
    │   ├── label_class.py       # LabelClass, Subclass
    │   └── annotation.py        # Annotation, AnnotationType (enum)
    ├── tools/
    │   ├── base.py              # BaseTool ABC
    │   ├── select_tool.py       # SelectTool
    │   └── polygon_tool.py      # PolygonTool (Phase 1)
    ├── storage/
    │   └── project_store.py     # save/load .annproj directory
    ├── exporters/
    │   ├── base.py              # BaseExporter ABC
    │   └── yolo_seg.py          # (Phase 5) YOLO segmentation export
    └── plugins/
        └── base.py              # BasePlugin ABC (Phase 6)
```

---

## 4. Project file format — `.annproj/`

A project is a **directory** with the extension `.annproj`:

```
my_project.annproj/
├── project.json         # version, name, id, created_at, settings, classes
├── images.json          # image inventory: path, hash, width, height, split
└── annotations/
    ├── <image_stem>.json  # one file per image, array of Annotation objects
    └── ...
```

### project.json schema (v1)
```json
{
  "format_version": 1,
  "id": "<uuid>",
  "name": "my project",
  "created_at": "2026-05-28T10:00:00",
  "modified_at": "2026-05-28T10:00:00",
  "image_folder": "/absolute/or/relative/path",
  "classes": [
    { "id": 0, "name": "crack", "color": "#FF4444",
      "supercategory": null, "keypoint_names": [], "skeleton": [] }
  ],
  "settings": {
    "default_export_format": "yolo_seg",
    "autosave_interval_sec": 60
  }
}
```

### Annotation object schema
```json
{
  "id": "<uuid>",
  "class_id": 0,
  "type": "segment",
  "data": {
    "points": [[0.1, 0.2], [0.3, 0.4], ...]
  },
  "meta": {
    "created_at": "...",
    "tool": "polygon",
    "source": "manual"
  }
}
```

---

## 5. Tool system

```python
class BaseTool(ABC):
    @abstractmethod
    def on_press(self, scene_pos, modifiers): ...
    @abstractmethod
    def on_move(self, scene_pos, modifiers): ...
    @abstractmethod
    def on_release(self, scene_pos, modifiers): ...
    @abstractmethod
    def on_double_click(self, scene_pos, modifiers): ...
    @abstractmethod
    def on_key(self, key, modifiers): ...
    def activate(self): ...      # called when tool becomes active
    def deactivate(self): ...    # called when switching away
    def cursor(self) -> QCursor: ...
```

The `AnnotationScene` holds an `active_tool: BaseTool` and forwards all mouse/key events to it.

---

## 6. Undo/redo (Phase 1)

Use Qt's `QUndoStack` + `QUndoCommand` subclasses:
- `AddAnnotationCommand`
- `DeleteAnnotationCommand`
- `MoveVertexCommand`
- `ChangeClassCommand`

---

## 7. ML backend isolation (Phase 7)

ML features (SAM, auto-label, YOLO inference) must:
- Never be imported in the base runtime.
- Run in a subprocess with a defined JSON RPC protocol OR a local REST service.
- Be configured with a separate Python interpreter path (system Python / conda env / uv env).

---

## 8. Phase delivery mapping

| Phase | Key deliverables |
|-------|-----------------|
| 0 | Workspace, audit, architecture, runnable skeleton |
| 1 | Project model, image list, polygon/bbox/polyline tools, save/load, undo/redo |
| 2 | Settings manager, import/export of project settings, schema versioning |
| 3 | Segmentation, keypoints/skeletons, OBB |
| 4 | Validation, QC, dataset statistics |
| 5 | YOLO, COCO, VOC, LabelMe, mask, CSV exporters |
| 6 | Plugin API + Crack Tool proof-of-concept |
| 7 | ML backend: SAM, YOLO auto-label, external env support |
| 8 | Video, tracking, review workflows |
