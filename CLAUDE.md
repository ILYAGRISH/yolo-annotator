# Project memory

## Workspace
This workspace contains:
- `old_app/` — frozen reference implementation
- `new_annotator/` — the new production codebase
- `shared_tests/` — shared datasets and manual regression checks
- `docs/` — specs, phases, and design notes

## Migration rules
- Build new features only in `new_annotator/`.
- Use `old_app/` only for audit, comparison, regression checks, and selective reuse.
- Do not copy legacy architecture into `new_annotator/`.
- If you want to reuse code from `old_app/`, explain why first.

## Workflow rules
- Work strictly phase by phase.
- Complete one phase, then stop.
- After each phase, provide:
  - summary of changes
  - file list
  - run commands
  - manual test steps
  - risks / limitations
  - proposal for the next phase
- Do not start the next phase until explicitly approved.

## Architecture rules
- Keep clean boundaries between UI, domain, storage, import/export, plugins, and ML integration.
- Do not use YOLO/COCO/VOC as the primary internal storage model.
- Keep the base runtime `.venv`-friendly.
- Heavy ML integrations must be isolated behind a separate backend/environment layer.

## Specs
Main roadmap:
- `@docs/annotator-roadmap.md`