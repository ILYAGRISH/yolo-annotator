"""Pre-labelling settings, stored per project in <project>/ml_prelabel.json:
the last model, thresholds, which images to process and — per model — how
its classes map onto project classes."""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path

FILE_NAME = "ml_prelabel.json"

EXISTING_SKIP = "skip"          # images that already have annotations are left alone
EXISTING_REPLACE = "replace"    # earlier model annotations are replaced, manual ones kept
EXISTING_ADD = "add"            # always add


@dataclass
class PrelabelSettings:
    model: str = ""
    conf: float = 0.25
    iou: float = 0.7
    imgsz: int = 0                    # 0 = the model's own training size
    simplify_px: float = 2.0
    kpt_threshold: float = 0.5
    existing: str = EXISTING_SKIP
    scope: str = "all"                # all / train / val / test
    # normalised model path -> {model class id (str): project class id | None}
    mappings: dict = field(default_factory=dict)

    # ── mapping per model ─────────────────────────────────────────────────────

    @staticmethod
    def _key(model: str) -> str:
        return os.path.normcase(os.path.abspath(model)) if model else ""

    def mapping_for(self, model: str) -> dict[int, int | None] | None:
        raw = self.mappings.get(self._key(model))
        if raw is None:
            return None
        return {int(k): (int(v) if v is not None else None) for k, v in raw.items()}

    def set_mapping(self, model: str, mapping: dict[int, int | None]) -> None:
        self.mappings[self._key(model)] = {str(k): v for k, v in mapping.items()}

    # ── persistence ───────────────────────────────────────────────────────────

    @classmethod
    def load(cls, project_path: Path | None) -> "PrelabelSettings":
        if not project_path:
            return cls()
        try:
            data = json.loads((Path(project_path) / FILE_NAME).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return cls()
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in data.items() if k in known})

    def save(self, project_path: Path | None) -> None:
        if not project_path:
            return
        path = Path(project_path) / FILE_NAME
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(asdict(self), ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, path)
