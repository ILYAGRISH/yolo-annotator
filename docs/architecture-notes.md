# Architectural Notes for Annotator Project

## 1. Mixed Annotation Types in a Single Project

### Core principle

A single project — and even a single image — can contain multiple annotation types simultaneously:
- `bbox` (bounding box)
- `polygon` (instance segmentation)
- `polyline` (lines, cracks, edges)
- `obb` (oriented/rotated bounding box)
- `keypoints` (skeleton, pose)
- `classification` (image-level label)

This is intentional and must be supported at every level: project model, label storage, canvas rendering, and export subsystem.

---

## 2. Class Schema Design

### Two strictly separated concepts

| Concept | Description | Storage location |
|---|---|---|
| **Class schema** | Class definitions: name, ID, color, type, tools, attributes | `class_schema.json` in project root |
| **Annotation / label** | Geometry instance on a specific image, references class by ID | `labels/img_name.json` |

Annotations must reference class by **ID only**, never by name.
Renaming a class must not modify any label files.

### class_schema.json structure

```json
{
  "schema_version": "1.0",
  "classes": [
    {
      "id": 0,
      "name": "crack",
      "color": "#FF4444",
      "annotation_type": "polygon",
      "allowed_tools": ["polygon", "crack_tool"],
      "subclasses": ["longitudinal", "transverse", "alligator"],
      "attributes": [
        {
          "name": "severity",
          "type": "select",
          "options": ["low", "medium", "high"]
        }
      ],
      "display_style": {
        "opacity": 0.5,
        "line_width": 2
      }
    },
    {
      "id": 1,
      "name": "car",
      "color": "#4488FF",
      "annotation_type": "obb",
      "allowed_tools": ["obb"],
      "subclasses": [],
      "attributes": [],
      "display_style": {
        "opacity": 0.6,
        "line_width": 2
      }
    }
  ]
}
```

### Class editing rules

| Action | Safety | Required behavior |
|---|---|---|
| Rename class | Safe | Update schema only, label files untouched |
| Change color / style | Safe | Display update only |
| Change annotation_type | Dangerous | Warn: N labels exist for this class. Require explicit confirmation. |
| Delete class | Dangerous | Warn: N labels will be affected. Offer reassign or delete all. |
| Add new class | Safe | Append to schema, assign next available ID |
| Edit ID manually | Forbidden | IDs are internal and immutable |

---

## 3. Internal Label Format

Each image has one label file in `labels/` using the project's own internal format (not YOLO/COCO/VOC).
Export to external formats is handled only by the export subsystem.

The annotation model must be **polymorphic** — each annotation object stores its own geometry type:

```json
{
  "image": "img001.jpg",
  "annotations": [
    {
      "id": 1,
      "class_id": 0,
      "type": "polygon",
      "geometry": [[0.10, 0.20], [0.15, 0.30], [0.20, 0.25]]
    },
    {
      "id": 2,
      "class_id": 1,
      "type": "obb",
      "geometry": {
        "cx": 0.50, "cy": 0.35,
        "w": 0.12, "h": 0.06,
        "angle": 30.0
      }
    },
    {
      "id": 3,
      "class_id": 2,
      "type": "polyline",
      "geometry": [[0.10, 0.80], [0.20, 0.75], [0.35, 0.70]]
    },
    {
      "id": 4,
      "class_id": 3,
      "type": "keypoints",
      "geometry": [
        {"x": 0.30, "y": 0.40, "v": 2},
        {"x": 0.32, "y": 0.55, "v": 1}
      ]
    }
  ]
}
```

`type` field is mandatory in every annotation record.
Do not infer annotation type from `class_id` alone — a class may allow multiple tools.

---

## 4. Project Folder Structure

```
my_project/
  project.json          <- project meta, canvas settings, tool config, export profiles
  class_schema.json     <- all class definitions (portable, exportable separately)
  labels/
    img001.json         <- internal format, one file per image
    img002.json
  images/
    img001.jpg
    img002.jpg
```

`class_schema.json` can be exported and imported independently for transfer to another computer or project.

---

## 5. Class Schema Import / Export

- Export `class_schema.json` as a standalone portable file.
- Import into another project with conflict resolution:

| Conflict type | Resolution |
|---|---|
| Same name, different ID | Offer merge / replace / skip |
| Same ID, different name | Apply automatic ID remapping, update all label references |
| New class, no conflict | Append directly |

- Schema file must include `schema_version`.
- On import, run migration logic if `schema_version` differs from current.
- Import modes: **merge** (add missing classes) or **replace** (overwrite entire schema with confirmation).

---

## 6. Mixed Dataset Export Strategy

### The core constraint

**YOLO supports only one task type per dataset.**
A single YOLO export cannot mix `detect`, `segment`, `obb`, `pose`, and `classify` annotations.

### Solution: multiple exports from one project

One project with mixed annotations → multiple filtered exports → multiple models:

```
my_project/  (mixed: bbox + polygon + obb + keypoints)
    |
    +-- export --> dataset_detect/    --> train YOLO detect  --> model_detect.pt
    +-- export --> dataset_segment/   --> train YOLO segment --> model_segment.pt
    +-- export --> dataset_obb/       --> train YOLO obb     --> model_obb.pt
    +-- export --> dataset_pose/      --> train YOLO pose    --> model_pose.pt
```

Each export filters annotations by type and generates its own `labels/` and `data.yaml`.

### Shared images optimization

Images can be shared across exports without duplication:

```
exports/
  images/                    <- shared image pool (symlinks or references)
  labels_detect/             <- bbox labels only
  labels_segment/            <- polygon labels only
  labels_obb/                <- obb labels only
  dataset_detect.yaml        <- points to images/ + labels_detect/
  dataset_segment.yaml       <- points to images/ + labels_segment/
  dataset_obb.yaml           <- points to images/ + labels_obb/
```

Each `data.yaml` points to the shared `images/` and its own `labels_*` folder.
No image duplication. Only label files differ per export.

## Dop

### Shared images mode — implementation detail

When exporting multiple datasets from one project, images must not be duplicated.

Required behavior:
- Generate one shared `images/` folder (or use symlinks/relative paths to original project images).
- Generate separate `labels_detect/`, `labels_segment/`, `labels_obb/` etc. folders — one per export type.
- Generate one `data.yaml` per export type, each pointing to the shared `images/` and its own `labels_*/` folder.
- If the user selects "copy images" mode — copy once into shared `images/`, not once per dataset.

Export subsystem must filter annotations by `annotation_type` before writing each `labels_*/` folder:
- `labels_detect/`  → only `bbox` annotations
- `labels_segment/` → only `polygon` annotations
- `labels_obb/`     → only `obb` annotations
- `labels_pose/`    → only `keypoints` annotations

If an image has no annotations of the selected type — write an empty label file (required by YOLO).
If a class has `annotation_type` that does not match the current export type — skip its annotations silently.


---

## 7. Multi-Model Inference Strategy

After training separate models, run inference sequentially or in parallel:

### Sequential (simple, low memory)
```python
result_detect  = model_detect(img)    # general objects, bounding boxes
result_segment = model_segment(img)   # road surface, damage zones
result_obb     = model_obb(img)       # aerial objects at angles
result_pose    = model_pose(img)      # structural keypoints
```

### Parallel (faster with multiple GPU / sufficient VRAM)
Run all models concurrently, merge results after inference.

### Typical pipeline for infrastructure inspection

| Model | Task | What it detects |
|---|---|---|
| YOLO detect | bbox | people, vehicles, general objects |
| YOLO segment | polygon | pavement zones, damage areas |
| YOLO obb | rotated bbox | aerial/oblique objects |
| YOLO pose | keypoints | structural feature points |

---

## 8. Export Subsystem Requirements (Phase 5)

The export subsystem must handle the mixed annotation case explicitly:

- On YOLO export: let user select which annotation types to include.
- Automatically split mixed projects into separate per-type datasets.
- Support `shared images` mode: generate multiple `labels_*/` folders, one `images/`, multiple `data.yaml` files.
- Generate one `data.yaml` per exported dataset with correct paths.
- Warn if a class has annotations of a type not matching its `annotation_type` in the schema.
- Support train/val/test split per export profile.
- Export profiles must be saveable and reusable within the project settings.

## Dop

- When exporting to YOLO format, show a warning:
  "Attributes will not be included in YOLO export. They are preserved in the project file."
- Attributes are internal metadata — they survive in `labels/*.json` as long as the project exists.
- Attributes are lost permanently only if the user exports to YOLO and deletes the original project.
- COCO export must include attributes via extra fields.
- Pascal VOC export must map standard attributes (`occluded`, `truncated`, `difficult`) to native VOC fields.


## 9. Annotation Types and Allowed Tools

### Matrix: annotation_type → allowed_tools

| `annotation_type` | Built-in tools | Custom tool examples |
|---|---|---|
| `bbox` | `bbox` | `smart_bbox` (SAM-based), `auto_bbox` (YOLO proposal) |
| `obb` | `obb` | `auto_obb` (SAM-based oriented box) |
| `polygon` | `polygon`, `polyline→polygon` | `crack_tool`, `brush`, `sam_polygon`, `magic_wand` |
| `polyline` | `polyline` | `crack_source` (raw crack line before buffering) |
| `keypoints` | `keypoints` | `auto_pose` (YOLO pose proposal) |
| `classification` | `classification` (label selector) | — |
| `mask` | `brush`, `eraser`, `polygon→mask` | `sam_mask` |

---

### Key rules

**`polyline` and `polygon` are adjacent but distinct types.**
`polyline` — an open line; the result remains a line geometry.
`polygon` — a closed area. The `crack_tool` belongs to the `polygon` type because its output is a polygon (the buffered line becomes a segmentation mask).

**One class — one `annotation_type`, but multiple `allowed_tools`.**
Example: class `road_damage` with `annotation_type: polygon` may allow `polygon` (manual), `sam_polygon` (AI-assisted), and `crack_tool` (custom via buffering). All three tools produce the same geometry type — a polygon.

**`mask` is a separate type**, visually similar to `polygon` but stored differently.
A mask is stored as a pixel mask (PNG or RLE), not as a vector. Support it separately, especially for semantic segmentation tasks.

---

### Tool constraint schema

Each class can optionally define per-tool constraints:

```json
{
  "annotation_type": "polygon",
  "allowed_tools": ["polygon", "crack_tool", "sam_polygon"],
  "tool_constraints": {
    "crack_tool": {
      "output_type": "polygon",
      "requires_source_geometry": "polyline"
    },
    "sam_polygon": {
      "output_type": "polygon",
      "requires_ml_backend": true
    }
  }
}
```

---

### Validation rule for custom tool registration

When registering a custom tool via the plugin API, the system must verify that the tool's declared `output_type` matches the `annotation_type` of any class it is assigned to.

A tool that produces `bbox` geometry must not appear as an allowed tool for a class with `annotation_type: polygon`.

This constraint must be enforced:
- at tool registration time
- when saving class schema changes
- before drawing begins (runtime check)

## 10. Crack Tool — Design Decisions (Phase 6)

---

### A. Source geometry storage

**Decision: store `source_geometry` and `tool_params` directly inside the annotation object.**

```json
{
  "id": 5,
  "class_id": 0,
  "type": "polygon",
  "tool": "crack_tool",
  "geometry": [[0.10, 0.20], [0.15, 0.30], [0.20, 0.25]],
  "source_geometry": {
    "type": "polyline",
    "points": [[0.10, 0.80], [0.20, 0.75], [0.35, 0.70]]
  },
  "tool_params": {
    "buffer_width": 0.008,
    "cap_style": "round",
    "join_style": "round",
    "simplify": 0.001
  }
}
```

**Why not a separate hidden polyline annotation:**
- Hidden objects pollute QC, statistics, and object counters.
- Deleting a polygon requires separately cleaning up the linked source — risk of orphan objects.
- Export subsystem would need to explicitly filter out "technical" annotations.
- A separate hidden annotation is only justified if the user needs to edit the source line as an independent object. For Crack Tool this is not required.

**Why inline is correct:**
- One object — all information. Polygon, buffer params, and source line live and are deleted together.
- The annotation is fully atomic and self-contained.
- Export subsystem simply ignores `source_geometry` and `tool_params` — they never appear in YOLO/COCO/VOC output.

**Export rule (mandatory):**
All fields except `class_id`, `type`, and `geometry` are considered internal-only.
The export subsystem must explicitly filter them out for every export format.
Models train on exported files only — `source_geometry` and `tool_params` never reach the training pipeline.

---

### B. Plugin registration strategy

**Decision: implement Crack Tool as a built-in tool using the `BaseTool` interface — which becomes the future plugin API — but without a dynamic plugin loader in Phase 6.**

```python
class CrackTool(BaseTool):
    name = "crack_tool"
    output_type = "polygon"
    requires_source_geometry = "polyline"

    def get_params_schema(self) -> dict: ...
    def draw(self, canvas, event): ...
    def compute_geometry(self, source_points: list, params: dict) -> list: ...
    def serialize(self, annotation: dict) -> dict: ...
```

`BaseTool` is the interface. Crack Tool implements it.
In Phase 6: tools are registered manually in code — no dynamic loading from a folder yet.
In Phase 7+: add a plugin loader that reads `plugins/*.py` and calls the same registration automatically.

**Why not a full plugin API with folder loading in Phase 6:**
Dynamic plugin loading adds complexity — sandboxing, versioning, dependency management.
That is a separate task. Build the correct interface first, then add the loader later.

**Registration flow (Phase 6):**
```python
tool_registry.register(CrackTool())
```

**Registration flow (Phase 7+):**
```python
for plugin_file in Path("plugins/").glob("*.py"):
    tool = load_plugin(plugin_file)
    tool_registry.register(tool)
```

Same `BaseTool` interface in both phases. The only difference is how registration is triggered.

---

### C. Tool parameters UI

**Decision: contextual Tool Properties panel — visible only when a tool is active.**

Placement: below the toolbar, above the canvas (or in the right sidebar).

```
[Toolbar: Select | BBox | Polygon | Polyline | OBB | Crack | ...]
──────────────────────────────────────────────────────────────────
[Tool Properties — shown only when a parameterized tool is active]
  Buffer width:  [slider]  0.008
  Cap style:     [Round ▼]
  Join style:    [Round ▼]
  Simplify:      [0.001  ]
──────────────────────────────────────────────────────────────────
[Canvas]
```

**Behavior:**
- Parameters apply in **real time** — changing buffer width immediately recomputes and previews the polygon on canvas.
- The Apply button finalizes the annotation into the label file.
- Reset restores the last saved `tool_params` for that annotation.
- When no parameterized tool is active, the Tool Properties panel is hidden or collapsed.

**Tool params schema:**
Each tool declares its own params schema via `get_params_schema()`.
The UI renders controls dynamically from this schema — no hardcoded UI per tool.
This allows future custom tools to have their own parameters without UI changes.

```python
def get_params_schema(self):
    return {
        "buffer_width": {"type": "float", "min": 0.001, "max": 0.1, "default": 0.008, "label": "Buffer width"},
        "cap_style":    {"type": "select", "options": ["round", "flat", "square"], "default": "round"},
        "join_style":   {"type": "select", "options": ["round", "mitre", "bevel"], "default": "round"},
        "simplify":     {"type": "float", "min": 0.0, "max": 0.01, "default": 0.001, "label": "Simplify tolerance"}
    }
```

