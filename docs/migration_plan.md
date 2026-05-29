# Migration Plan — old_app → new_annotator

Audit date: 2026-05-28  
Audited codebase: `old_app/`

---

## 1. What exists in old_app

| File | Purpose |
|------|---------|
| `main.py` | QApplication entry point + dark Fusion palette |
| `app/models/annotation.py` | `AnnotationType` enum, `LabelClass`, `SegmentAnnotation` dataclass |
| `app/io/yolo_format.py` | `load_labels` / `save_labels` for YOLO txt |
| `app/canvas/canvas_scene.py` | `AnnotationScene(QGraphicsScene)` — draw loop, tool mode FSM |
| `app/canvas/canvas_view.py` | `AnnotationView(QGraphicsView)` — wheel zoom, MMB pan |
| `app/canvas/items/polygon_item.py` | `PolygonAnnotationItem(QGraphicsItem)` — rendering + vertex handles |
| `app/panels/file_panel.py` | Folder picker + image list with labeled/unlabeled coloring |
| `app/panels/class_panel.py` | Editable class list with color picker dialog |
| `app/panels/annotation_panel.py` | Per-image annotation list |
| `app/main_window.py` | `QMainWindow` — wires all panels, shortcuts, save/load |

---

## 2. REUSE — take directly (with namespace move)

| Component | Reason |
|-----------|--------|
| `canvas_view.py` | Wheel zoom + MMB pan is a pure Qt utility with no business logic coupling. Copy verbatim into `new_annotator/annotator/ui/canvas/view.py`. |
| `polygon_item.py` | Rendering logic (fill, outline, vertex handles, hover) is UI-only. Copy into `new_annotator/annotator/ui/canvas/items/polygon_item.py` — but decouple it from `SegmentAnnotation` (item should accept a plain list of points). |
| Dark Fusion palette setup in `main.py` | Copy into `new_annotator/annotator/app.py`. |

---

## 3. REFACTOR — worth keeping but needs significant rework

| Component | Issue | New approach |
|-----------|-------|--------------|
| `canvas_scene.py` | Tool logic (polygon FSM, vertex drag) is baked directly into the scene. Hard to extend. | Extract tool logic into a `BaseTool` / `PolygonTool` class. Scene delegates all input to the active tool. |
| `class_panel.py` | `_add()` is a private method called from `main_window.py` — breaks encapsulation. Color auto-assignment is global. | Make class management part of the domain `Project` model. Panel is only a view. |
| `file_panel.py` | Label folder is derived from image folder path heuristic — brittle. Reload re-scans every time. | Image inventory managed by `Project` domain object. Panel subscribes to project events. |
| `annotation_panel.py` | Good structure but tightly coupled to `SegmentAnnotation`. | Generalize to any `Annotation` type via a display adapter. |

---

## 4. REPLACE — do not carry over

| Component | Reason |
|-----------|--------|
| `app/models/annotation.py` (as primary store) | The new internal format is NOT YOLO-derived. `SegmentAnnotation` with `(x,y)` normalized lists stays only as an export artifact. The internal model is `Annotation` with an explicit `AnnotationType` and a structured `data` dict (or typed subclasses). |
| `app/io/yolo_format.py` (as primary I/O) | Move to `new_annotator/annotator/exporters/yolo.py` as a pure exporter. Never used for internal save/load. |
| Direct file scan in `FilePanel` | Replaced by `Project.image_inventory` — a tracked list of images with metadata. |
| Saving annotations directly to `.txt` on every operation | Replaced by `ProjectStore.save()` — explicit save to the project directory format. |

---

## 5. UNKNOWN / TO DECIDE

| Question | Options | Decision needed by |
|----------|---------|-------------------|
| Internal project format | (a) Single `.json` file; (b) directory `.annproj/`; (c) SQLite | Phase 1 |
| Undo/redo approach | (a) Qt `QUndoStack`; (b) event sourcing; (c) copy-on-write snapshots | Phase 1 |
| Image references | Store absolute paths? Relative paths? Copy images into project? | Phase 1 |
| Plugin discovery | Entry points via `importlib.metadata`; simple folder scan; explicit registration | Phase 6 |
| ML backend isolation | Subprocess call; REST API to local server; dedicated `ml_backend/` package | Phase 7 |

---

## 6. Summary

- **Direct reuse**: ~2 files (view, polygon item rendering)
- **Refactor**: ~3 files (scene → tool system, class panel, file panel)
- **Replace**: ~3 files (annotation model, YOLO I/O as primary, direct file scan)
- **Net new**: domain model, storage, tool system, exporter ABC, plugin ABC, ML backend layer
