## Phase 3 — Advanced annotation types + Class schema architecture

### Class schema design

Separate two concepts strictly:

**Class schema** — definitions stored in project settings:
- class ID (immutable after creation, never editable by user)
- name
- color
- annotation_type (bbox / polygon / polyline / obb / keypoints / classification)
- allowed_tools (list of tool IDs permitted for this class)
- subclasses (list of string labels)
- attributes (additional per-annotation fields: select, text, number, bool)
- display_style (opacity, line_width, fill_color)

**Annotation** — instance stored in label data:
- references class by ID only, never by name
- renaming a class must not touch any label records

Store class schema in a dedicated file, separate from label data.
Internal label format is the project's own format (not YOLO/COCO/VOC).
Export to external formats happens via the export subsystem only.
my_project/
project.json ← project meta, canvas settings, tool config
class_schema.json ← all class definitions
labels/
img001.json ← internal project format
img002.json
images/
img001.jpg

text

### Class editing rules

Handle these scenarios explicitly:

| Action | Safety | Required behavior |
|---|---|---|
| Rename class | Safe | Update schema only, label files untouched |
| Change color / style | Safe | Display update only |
| Change annotation_type | Dangerous | Warn: X labels already exist for this class. Require explicit confirmation. |
| Delete class | Dangerous | Warn: X labels will be affected. Offer reassign to another class or delete all. |
| Add new class | Safe | Append to schema, assign next available ID |
| Edit ID manually | Forbidden | IDs are internal and immutable |

### Class schema import / export

- Export class_schema.json as a standalone portable file.
- Import into another project with conflict resolution:
  - conflict by name: offer merge / replace / skip
  - conflict by ID: apply automatic ID remapping, update all label file references
- Schema file must include a `schema_version` field.
- On import, run migration if schema_version differs.

### What to implement in this phase

- Class schema editor UI (add / edit / delete / reorder classes)
- Subclass editor
- Per-class attribute editor
- annotation_type and allowed_tools assignment per class
- Export class_schema.json
- Import class_schema.json with conflict resolution dialog
- schema_version field + migration logic
- Label model stores class_id reference only
- Rename / delete class with safety warnings and reassign dialog

### Acceptance criteria

- Renaming a class does not break any existing labels
- Deleting a class shows count of affected labels and requires confirmation
- class_schema.json can be exported and imported on another machine
- ID conflicts on import are resolved automatically with remapping
- schema_version is present and checked on import
- Internal label format in labels/ is independent from any export format