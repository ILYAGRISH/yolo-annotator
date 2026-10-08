"""
Review status of model-made annotations (Phase 8-A).

An annotation made by a model (meta.source == "model", pre-labelling) starts
UNREVIEWED. It becomes reviewed when a person accepts it (R / Shift+R) or edits
it — the status lives in meta, so old projects load unchanged:

    meta["reviewed"]    = True
    meta["reviewed_at"] = ISO time (UTC)
    meta["reviewed_by"] = user name (only when known)

Manual annotations (and SAM ones — the person chose the object) have no review
status: they are never "unreviewed".
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from annotator.domain.annotation import Annotation

SOURCE_MODEL = "model"
REVIEW_KEYS = ("reviewed", "reviewed_at", "reviewed_by")


def is_model(ann: Annotation) -> bool:
    return ann.meta.get("source") == SOURCE_MODEL


def is_reviewed(ann: Annotation) -> bool:
    return bool(ann.meta.get("reviewed"))


def is_unreviewed(ann: Annotation) -> bool:
    """A model annotation nobody has accepted or edited yet."""
    return is_model(ann) and not is_reviewed(ann)


def count_unreviewed(annotations) -> int:
    return sum(1 for a in annotations if is_unreviewed(a))


def reviewed_meta(meta: dict, reviewed: bool = True, by: str = "") -> dict:
    """A copy of `meta` with the review status set (True) or cleared (False)."""
    out = {k: v for k, v in meta.items() if k not in REVIEW_KEYS}
    if reviewed:
        out["reviewed"] = True
        out["reviewed_at"] = datetime.utcnow().isoformat()
        if by:
            out["reviewed_by"] = by
    return out


def drop_unreviewed(all_annotations: dict) -> dict:
    """{image: [Annotation]} without unreviewed model annotations (export)."""
    return {img: [a for a in anns if not is_unreviewed(a)]
            for img, anns in all_annotations.items()}


def count_unreviewed_in_file(path: Path) -> int:
    """Unreviewed model annotations in one annotations/<stem>.json — cheap:
    files without a model annotation are not parsed."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return 0
    if f'"{SOURCE_MODEL}"' not in text:
        return 0
    try:
        items = json.loads(text)
    except ValueError:
        return 0
    return sum(1 for d in items
               if isinstance(d, dict)
               and (d.get("meta") or {}).get("source") == SOURCE_MODEL
               and not (d.get("meta") or {}).get("reviewed"))
