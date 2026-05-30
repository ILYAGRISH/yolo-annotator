---
name: YOLO Labeler / Annotator project
description: Desktop annotation tool at d:\Label_segment — two codebases: old_app (frozen prototype) and new_annotator (production build in phases)
type: project
originSessionId: e6699982-26de-4b82-b844-142014a2fe28
---
## Workspace layout
```
d:\Label_segment\
├── old_app/          — frozen reference prototype (PyQt6, YOLO seg only)
├── new_annotator/    — production build (phase-by-phase)
├── shared_tests/     — regression fixtures (to be populated)
├── docs/
│   ├── annotator-roadmap.md      — product spec + phase plan
│   ├── architecture.md           — architecture decisions
│   ├── architecture-notes.md     — §1-10: tool matrix, mask type, tool_constraints, Crack Tool decisions
│   ├── migration_plan.md         — reuse/refactor/replace audit
│   ├── Dop_Fhase2-3.md           — user's spec additions (class schema, attributes, display_style)
│   ├── patch_phase3.md           — patch: annotation_type immutable + tool enforcement in toolbar
│   ├── About.md                  — user-facing description of annotation types and QC
│   ├── phase{1-6}_completion_ru.md + phase5dop_completion_ru.md
│   ├── phase7c_completion_ru.md  — COCO export + CrackEdit + Plugin loader
│   ├── phase7a_completion_ru.md  — POSE instrument + YOLO Pose export
│   └── Test_Help.md              — план ручного тестирования всех функций
├── Example/          — sample marble image + YOLO seg labels (all class 0)
└── CLAUDE.md         — workspace + workflow rules
```

## Current status: Phase 7A complete ✅

### Completed phases
- **Phase 0** — workspace, audit, architecture, skeleton
- **Phase 1** — domain model, image list, polygon/bbox/polyline tools, save/load, undo/redo. Test: 35/35.
- **Phase 2** — YOLO auto-export, autosave timer, FORMAT_VERSION=2.
- **Phase 3** — Class schema redesign, schema editor UI, safe delete/reassign, export/import with conflict resolution. FORMAT_VERSION=3, SCHEMA_VERSION=1.
- **Patch 3.1** — annotation_type immutable; tool enforcement in toolbar.
- **Phase 4** — Validation layer, QCPanel, export JSON/CSV. Test: 29/29.
- **Phase 5** — OBB tool, YOLO detect/seg/OBB exporters, train/val/test split, Export Dataset dialog. Test: 74/74.
- **Phase 5 supplement** — YOLO attribute warning, type mismatch warning before export.
- **Phase 6** — Crack Tool [C] + Tool Properties Panel. Test: 58/58.
- **Phase 7C** — COCO Instances export, CrackTool edit mode, Plugin loader. Test: 79/79.
- **Phase 7A** — POSE instrument [K] + YOLO Pose export + Skeleton schema editor. Test: 109/109.

### Local git repo
- `d:\Label_segment` — initialized, commit 5faa3b0 (Phase 7A + Test_Help.md)
- Remote not yet added (planned for end of project)

### Next: Phase 7 ML backend (SAM/YOLO auto-label) — to be discussed carefully

## new_annotator/ key files
```
new_annotator/
├── main.py / run.bat / install.bat
├── requirements.txt          — PyQt6, Pillow, shapely>=2.0.0
├── test_phase1.py            — integration test (35/35 checks, Phase 1-3)
├── test_phase4.py            — validation tests (29/29 checks)
├── test_phase5.py            — export + OBB tests (74/74 checks)
├── test_phase6.py            — Crack Tool + buffer + export safety (58/58 checks)
├── test_phase7.py            — COCO + CrackEdit + Plugin loader (79/79 checks)
├── test_phase7a.py           — POSE + YOLO Pose export (109/109 checks)
└── annotator/
    ├── app.py
    ├── domain/
    │   ├── annotation.py      — Annotation, AnnotationType (SEGMENT, POLYLINE, BBOX, OBB, POSE, CLASSIFY)
    │   ├── label_class.py     — LabelClass + SkeletonKeypoint + ANNOTATION_TYPE_TOOLS
    │   ├── class_schema.py    — ClassSchema, SCHEMA_VERSION=1
    │   └── project.py         — Project, ProjectSettings, ImageRecord (split field). FORMAT_VERSION=3
    ├── storage/
    │   └── project_store.py   — .annproj dir; class_schema.json separate
    ├── exporters/
    │   ├── base.py            — BaseExporter ABC + write_yolo_dataset() + _write_data_yaml()
    │   ├── yolo_seg.py        — per-image auto-export + full project export
    │   ├── yolo_detect.py     — YOLO detect: class_id cx cy w h
    │   ├── yolo_obb.py        — YOLO OBB: class_id x1 y1 x2 y2 x3 y3 x4 y4 (4 rotated corners)
    │   ├── yolo_pose.py       — YOLO Pose: class_id cx cy w h kx ky v ... + kpt_shape in yaml
    │   └── coco.py            — COCO Instances JSON per split, attributes included
    ├── controller/
    │   └── project_controller.py — export_dataset (yolo_detect/seg/obb/pose/coco)
    ├── validation/
    │   ├── base.py / validator.py / rules/{empty_image,small_polygon,duplicate}.py
    ├── tools/
    │   ├── base.py / select_tool.py / polygon_tool.py / bbox_tool.py / obb_tool.py
    │   ├── crack_tool.py      — CrackTool [C]: polyline→buffer→SEGMENT; start_edit for source editing
    │   └── pose_tool.py       — PoseTool [K]: click=keypoint, skeleton-guided auto-commit
    ├── plugins/
    │   ├── loader.py          — auto-discovers BaseTool subclasses from plugins/*.py
    │   └── example_tool.py    — stub plugin для демонстрации API
    ├── ui/
    │   ├── undo/commands.py
    │   ├── canvas/
    │   │   ├── scene.py / view.py
    │   │   └── items/ (base_item, polygon_item, bbox_item, obb_item, pose_item)
    │   ├── panels/
    │   │   ├── images_panel.py      — split context menu (RMB)
    │   │   ├── classes_panel.py
    │   │   ├── annotations_panel.py — Edit source button (crack)
    │   │   ├── qc_panel.py
    │   │   └── tool_props_panel.py  — dynamic controls from get_params_schema()
    │   ├── dialogs/
    │   │   ├── new_project_dialog.py
    │   │   ├── class_schema_editor.py — + Skeleton GroupBox for keypoints classes
    │   │   ├── class_delete_dialog.py
    │   │   ├── class_import_dialog.py
    │   │   └── export_dialog.py     — YOLO detect/seg/obb/pose + COCO
    │   └── main_window.py      — все инструменты [V/P/L/B/O/C/K] + plugin loader
```

## Annotation types status
| Type | Tool | Canvas item | Export |
|------|------|-------------|--------|
| BBOX | BBoxTool [B] | BBoxAnnotationItem | ✅ YOLO detect + seg |
| SEGMENT | PolygonTool [P] | PolygonAnnotationItem | ✅ YOLO seg |
| POLYLINE | PolylineTool [L] | PolygonAnnotationItem | ✅ YOLO seg |
| OBB | OBBTool [O] | OBBAnnotationItem | ✅ YOLO obb |
| SEGMENT (crack) | CrackTool [C] | PolygonAnnotationItem | ✅ YOLO seg (source_geometry stripped) |
| POSE | PoseTool [K] | PoseAnnotationItem | ✅ YOLO pose (bbox auto-computed) |
| CLASSIFY | ❌ not yet | ❌ not yet | ❌ not yet |

## CrackTool design (Phase 6)
- Source geometry stored inline in ann.data["source_geometry"] (not as separate annotation)
- tool_params stored inline in ann.data["tool_params"]
- Buffer computed by shapely.LineString.buffer() in pixel coords, normalized back
- buffer_width = normalized × min(image_w, image_h) → pixels
- Export safety: YOLO exporters read only data["points"], source_geometry never leaks
- Hotkey: C. Workflow: click=add point, RMB=undo last, Enter/dbl-click=commit, Esc=cancel

## Tool Properties Panel (Phase 6)
- Location: fixed 36px strip below toolbar, above canvas
- Hidden when non-parameterized tool is active
- Controls rendered dynamically from tool.get_params_schema():
  - float → QDoubleSpinBox
  - select → QComboBox
- Emits params_changed(dict) → main_window → tool.set_params() → live preview update

## PoseTool design (Phase 7A)
- Skeleton defined per class: `SkeletonKeypoint(name, edges: list[int])` in `LabelClass.skeleton`
- PoseTool [K]: click=place keypoint (v=2), RMB=undo, Enter/dbl-click=commit, Esc=cancel
- Skeleton-guided: auto-commits when all N points placed; pads shorter sequences with v=0
- YOLO Pose format: `class_id cx cy w h kx ky v ...`; bbox auto from visible keypoints + 5% margin
- `kpt_shape: [N, 3]` appended to data.yaml when skeleton defined
- Skeleton editor in Class Schema Editor: keypoint names list + edges text field `"0-1, 1-2, ..."`

## Export pipeline
- File > Export Dataset… [Ctrl+E] → ExportDatasetDialog
  - Shows attribute warning if any class has attributes
  - Shows mismatch warning if ann_type ≠ class.annotation_type
- Formats: YOLO detect / YOLO segment / YOLO obb
- Output: labels/{split}/*.txt + images/{split}/* (if copy_images) + data.yaml

## Tech stack
- Python 3.13 (C:\Python313), run via `py -3`
- PyQt6 + Pillow + shapely>=2.0.0
- new_annotator has its own .venv at new_annotator/.venv
- Run: `cd new_annotator && run.bat`
- Test: `cd new_annotator && .venv\Scripts\python test_phase6.py`
