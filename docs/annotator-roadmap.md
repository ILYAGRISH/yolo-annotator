Work in the current project folder and create a shared workspace here.

Goal:
Build a new desktop image annotation app step by step, while preserving the current quick prototype as a reference implementation. We will complete one phase at a time, review it, and only then move to the next phase.

Workspace strategy:
- Create a shared workspace structure in the current folder.
- Put the current app into `old_app/` as a frozen reference implementation.
- Build the new architecture only in `new_annotator/`.
- Do not merge the old architecture into the new one.
- Reuse code from `old_app/` only if it is clearly isolated and worth migrating.

Important safety rule:
If the current app already lives in the current folder, do not break git history or move files blindly. First propose a safe migration plan for creating:
- `old_app/`
- `new_annotator/`
- `shared_tests/`
- `migration_plan.md`
- `CLAUDE.md`

Main product goal:
Create a desktop annotation tool for computer vision datasets, optimized for YOLO workflows first, but designed with an internal project format and extensible architecture.

Core requirements:
- Desktop app in Python.
- Simple features should run from a normal `.venv`.
- Heavy ML features must use a separate backend layer with optional external Python environments (system Python / conda / uv / custom interpreter).
- Main entity = Project.
- A Project must contain images, annotations, project settings, classes/subclasses, colors, styles, tools, export profiles, hotkeys, skeleton templates, and custom tool parameters.
- Project settings must be exportable/importable for transfer to another computer.
- Internal project format must be independent from YOLO/COCO/VOC export formats.

Required architecture layers:
- UI shell
- canvas / interaction layer
- project domain model
- annotation domain model
- tool system
- import/export subsystem
- validation/QC subsystem
- plugin subsystem
- ML integration subsystem
- persistence layer

Mandatory custom tool design:
Support future custom tools through a plugin/tool API.
Include one required proof-of-concept custom tool:
- Crack Tool
- User draws a line/polyline
- Tool applies configurable buffering
- Generates a polygon segmentation annotation
- Source line remains editable
- Polygon can be rebuilt when parameters change

Development process:
Before coding, do Phase 0 only.

Phase 0:
1. Audit the current app.
2. Create the shared workspace structure.
3. Write `migration_plan.md` with:
   - reuse
   - refactor
   - replace
   - unknown
4. Write `architecture.md` for the new app.
5. Bootstrap `new_annotator/` with a clean runnable app skeleton and `.venv`-friendly setup.
6. Do not implement advanced features yet.

After Phase 0, stop and report:
- what you changed
- what files were created
- what can be reused from `old_app/`
- risks / unknowns
- exact commands to run
- manual test steps
- a short proposal for Phase 1

Phased roadmap:
- Phase 0: workspace, audit, architecture baseline
- Phase 1: Project model, image list, classes/subclasses, colors, bbox/polygon/polyline, save/load, undo/redo
- Phase 2: project settings manager, import/export of project settings, schema versioning
- Phase 3: segment / keypoints / skeletons / OBB
- Phase 4: validation, QC, dataset statistics
- Phase 5: import/export formats (YOLO, COCO, VOC, LabelMe, masks, CSV)
- Phase 6: plugin API and Crack Tool
- Phase 7: ML backend integration with external Python environments, auto-label hooks, SAM/YOLO integration
- Phase 8: advanced/rare features like video, tracking, review workflows

Rules:
- One phase at a time.
- Stop after each phase and wait for approval.
- Keep boundaries clean.
- Do not use YOLO txt as the primary storage format.
- Do not add heavy ML dependencies into the base runtime unless required.
- If you want to migrate code from `old_app/`, explain why first.
- If something is architecturally risky, discuss it before implementing.

Start with Phase 0 only.

## Dop

## Class immutability rules

Fields immutable after class creation:
- `id` — assigned automatically, never shown as editable input
- `annotation_type` — shown as read-only label after creation

Fields editable at any time:
- name, color, display_style, subclasses, attributes, allowed_tools

On class creation UI:
- show annotation_type as a dropdown (one-time selection)
- after saving — render it as plain text label, not an input

allowed_tools must only contain tools compatible with the class annotation_type.
The system must enforce this constraint — tools of wrong geometry type
must not appear as options for a given class.