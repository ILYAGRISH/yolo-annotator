"""
Validator — runs all validation rules and computes dataset statistics.
"""
from __future__ import annotations
import csv
import json
from datetime import datetime
from pathlib import Path

from annotator.domain.annotation import Annotation
from annotator.domain.project import Project
from annotator.validation.base import ValidationReport, ValidationRule
from annotator.validation.rules.duplicate import DuplicateAnnotationRule
from annotator.validation.rules.empty_image import EmptyImageRule
from annotator.validation.rules.small_polygon import SmallPolygonRule


def _default_rules() -> list[ValidationRule]:
    return [
        EmptyImageRule(),
        SmallPolygonRule(min_area=0.001),
        DuplicateAnnotationRule(iou_threshold=0.85),
    ]


def _compute_stats(
    project: Project,
    all_annotations: dict[str, list[Annotation]],
) -> dict:
    class_map = {c.id: c.name for c in project.classes}
    annotated: set[str] = set()
    total_anns = 0
    by_class: dict[str, int] = {}
    by_type: dict[str, int] = {}

    for img_path, anns in all_annotations.items():
        if anns:
            annotated.add(img_path)
        total_anns += len(anns)
        for ann in anns:
            cls_name = class_map.get(ann.class_id, str(ann.class_id))
            by_class[cls_name] = by_class.get(cls_name, 0) + 1
            t = ann.ann_type.value
            by_type[t] = by_type.get(t, 0) + 1

    total = len(project.images)
    ann_count = len(annotated)
    return {
        "total_images": total,
        "annotated_images": ann_count,
        "unannotated_images": total - ann_count,
        "coverage_pct": round(ann_count / total * 100, 1) if total else 0.0,
        "total_annotations": total_anns,
        "by_class": dict(sorted(by_class.items(), key=lambda x: -x[1])),
        "by_type":  dict(sorted(by_type.items(),  key=lambda x: -x[1])),
    }


class Validator:

    def __init__(self, rules: list[ValidationRule] | None = None):
        self.rules: list[ValidationRule] = rules if rules is not None else _default_rules()

    def run(
        self,
        project: Project,
        all_annotations: dict[str, list[Annotation]],
    ) -> ValidationReport:
        issues = []
        for rule in self.rules:
            issues.extend(rule.check(project, all_annotations))
        stats = _compute_stats(project, all_annotations)
        return ValidationReport(issues=issues, stats=stats)

    # ── export helpers ────────────────────────────────────────────────────────

    @staticmethod
    def export_json(report: ValidationReport, path: Path, project_name: str = ""):
        payload = {
            "project": project_name,
            "generated_at": datetime.utcnow().isoformat(),
            "stats": report.stats,
            "issues": [
                {
                    "severity": i.severity,
                    "rule": i.rule_name,
                    "image": Path(i.image_path).name,
                    "ann_id": i.ann_id or None,
                    "message": i.message,
                }
                for i in report.issues
            ],
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)

    @staticmethod
    def export_csv(report: ValidationReport, path: Path):
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["severity", "rule", "image", "ann_id", "message"])
            for i in report.issues:
                writer.writerow([
                    i.severity, i.rule_name,
                    Path(i.image_path).name,
                    i.ann_id or "",
                    i.message,
                ])
