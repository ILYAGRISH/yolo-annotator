# Phase 1 Completion Report

## Summary

Phase 1 delivers a fully working annotation editor with project management,
undo/redo, three annotation types (polygon/polyline/bbox), and a clean persistence
layer. The app launches and all core flows have been verified by an automated
integration test (23/23 checks pass).

---

## What Was Implemented

### Domain
| File | Change |
|------|--------|
| `annotator/domain/annotation.py` | Added `POLYLINE = "polyline"` to `AnnotationType` |

### Persistence
| File | Change |
|------|--------|
| `annotator/storage/project_store.py` | Already existed from Phase 0; used as-is |

### Undo / Redo
| File | Change |
|------|--------|
| `annotator/ui/undo/__init__.py` | New package |
| `annotator/ui/undo/commands.py` | `AddAnnotationCmd`, `DeleteAnnotationCmd`, `UpdateAnnotationCmd` — all mutations go through `QUndoStack` |

### Controller
| File | Change |
|------|--------|
| `annotator/controller/__init__.py` | New package |
| `annotator/controller/project_controller.py` | `ProjectController(QObject)` — single source of truth, owns `QUndoStack`, emits `project_changed / image_changed / annotations_changed / annotation_selected / status_message` |

### Tools
| File | Change |
|------|--------|
| `annotator/tools/select_tool.py` | Full implementation: click-to-select, drag vertex/handle, Delete removes, Escape deselects |
| `annotator/tools/polygon_tool.py` | `PolygonTool` + `PolylineTool` subclass — click=add, RMB=undo last, dbl-click/Enter=finish, Esc=cancel, snap-to-first |
| `annotator/tools/bbox_tool.py` | Drag-to-draw, dashed yellow preview, commits on release |

### Canvas Items
| File | Change |
|------|--------|
| `annotator/ui/canvas/items/__init__.py` | New package |
| `annotator/ui/canvas/items/base_item.py` | `BaseAnnotationItem` ABC |
| `annotator/ui/canvas/items/polygon_item.py` | `PolygonAnnotationItem` — segments (closed) and polylines (open), vertex handles, drag-to-edit, `to_data()` |
| `annotator/ui/canvas/items/bbox_item.py` | `BBoxAnnotationItem` — 4 corner handles, drag-to-resize, `to_data()` |

### Scene
| File | Change |
|------|--------|
| `annotator/ui/canvas/scene.py` | Replaced: `rebuild_annotations`, item registry `_ann_items`, selection API (`select_by_id`, `deselect_all`, etc.), event dispatch to active tool |

### Main Window
| File | Change |
|------|--------|
| `annotator/ui/main_window.py` | Replaced: owns `ProjectController`, wires undo/redo menu (Ctrl+Z/Y), exclusive tool toolbar with `QActionGroup`, keyboard shortcuts (V/P/L/B/F/A/D/Del/Esc), all panel ↔ controller signal connections |

### Test
| File | Change |
|------|--------|
| `test_phase1.py` | New integration test — 23 checks, runs headless (offscreen) |

---

## File Tree (new_annotator/annotator/)

```
annotator/
  controller/
    __init__.py
    project_controller.py
  domain/
    annotation.py          (POLYLINE added)
    label_class.py
    project.py
  storage/
    project_store.py
  tools/
    base.py
    select_tool.py
    polygon_tool.py
    bbox_tool.py
  ui/
    canvas/
      items/
        base_item.py
        polygon_item.py
        bbox_item.py
      scene.py
      view.py
    dialogs/
      new_project_dialog.py
    panels/
      annotations_panel.py
      classes_panel.py
      images_panel.py
    undo/
      commands.py
    main_window.py
  app.py
```

---

## Run Commands

```bat
cd new_annotator
install.bat          # first time only — creates .venv and installs PyQt6
run.bat              # launch the app
.venv\Scripts\python test_phase1.py   # run integration test
```

---

## Manual Test Steps

1. **New project** — File > New Project..., give a name and choose a folder.
2. **Add images** — File > Add Images from Folder..., select a folder with .jpg/.png.
3. **Select an image** in the left panel — it should appear on the canvas.
4. **Polygon tool (P)** — click to place vertices, double-click or Enter to close, Esc to cancel, RMB removes last point.
5. **BBox tool (B)** — drag a rectangle.
6. **Polyline tool (L)** — click points, double-click or Enter to finish.
7. **Select tool (V)** — click an annotation to select it; drag a vertex handle to edit shape; Delete removes it.
8. **Undo/Redo** — Ctrl+Z / Ctrl+Y after any add, edit, or delete.
9. **Save** — Ctrl+S or close the window — reopen the project and verify annotations are still there.
10. **A / D keys** — navigate to previous / next image.

---

## Known Limitations / Risks

- `LabelClass` objects are appended by name only (`project.add_class(name)` — no color picker UI yet); colors are auto-assigned from a palette. Full class editor is Phase 2.
- BBox minimum size is 4px — very small boxes are silently discarded.
- Double-click on polygon: Qt fires a press event before the double-click event, so the tool pops one duplicate point before committing. This is handled correctly but is a subtle coupling to Qt event ordering.
- No autosave timer yet (interval stored in settings, but no QTimer wired up).
- Images panel shows file names only; no thumbnail preview yet.

---

## Proposal for Phase 2

**Project settings manager**

- Class editor panel: add/rename/reorder/delete classes, pick colors (QColorDialog), assign supercategory.
- Export profile UI: choose format (YOLO seg, COCO, VOC), output folder, split ratios.
- Project settings serialization: export/import `settings.json` so a project config can be transferred to another computer.
- Schema versioning: bump `FORMAT_VERSION` and add a migration shim so older `.annproj` files load cleanly.
- Autosave timer wired to `ProjectSettings.autosave_interval_sec`.

Phase 2 adds no new annotation types — it completes the project management layer
that Phase 1 left skeletal.
