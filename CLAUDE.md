# Project memory

## Workspace
```
D:\Label_segment\          — git repo root (.git lives here)
├── new_annotator/         — PRODUCTION codebase (main app)
├── docs/                  — specs, phases, design notes
├── Archive/               — legacy prototypes (reference only, do not modify)
└── README.md
```

Run: `cd new_annotator && .venv\Scripts\python main.py`

## Rules
- Build new features only in `new_annotator/`.
- `Archive/` is frozen — do not modify or copy from it without explaining why first.
- Keep clean boundaries between UI, domain, storage, import/export, plugins, and ML integration.
- Do not use YOLO/COCO/VOC as the primary internal storage model.
- Heavy ML integrations must be isolated behind a separate backend/environment layer.

## Workflow
- Work strictly phase by phase.
- Complete one phase, then stop.
- After each phase, provide: summary of changes, file list, run commands, manual test steps, risks/limitations, proposal for the next phase.
- Do not start the next phase until explicitly approved.

## Specs
Main roadmap: `@docs/annotator-roadmap.md`
