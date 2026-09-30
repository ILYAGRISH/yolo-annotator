"""
Refresh ../Deploy — the ready-to-run copy of the app published on GitHub.

Run after every release:
    cd new_annotator
    .venv\\Scripts\\python build_deploy.py

Copied from the production sources (old copies are replaced):
    annotator/, plugins/, main.py, requirements.txt   ← new_annotator/
    About.md                                          ← docs/About.md

Deploy-only files are never touched: setup_venv.bat, run.bat, README.md,
.gitattributes (and a local .venv, if any).
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent            # new_annotator/
ROOT = SRC.parent                                # repo root
DEPLOY = ROOT / "Deploy"

DIRS = ["annotator", "plugins"]
FILES = ["main.py", "requirements.txt"]
DOCS = {ROOT / "docs" / "About.md": "About.md"}

_IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo")


def main() -> int:
    if not DEPLOY.is_dir():
        print(f"[ERROR] {DEPLOY} not found — create it with its setup scripts first")
        return 1

    for name in DIRS:
        dst = DEPLOY / name
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(SRC / name, dst, ignore=_IGNORE)
        n = sum(1 for p in dst.rglob("*") if p.is_file())
        print(f"  {name}/  ({n} files)")

    for name in FILES:
        shutil.copy2(SRC / name, DEPLOY / name)
        print(f"  {name}")

    for src, name in DOCS.items():
        shutil.copy2(src, DEPLOY / name)
        print(f"  {name}  (from {src.relative_to(ROOT)})")

    print(f"Deploy refreshed: {DEPLOY}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
