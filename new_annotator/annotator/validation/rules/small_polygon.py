from annotator.domain.annotation import AnnotationType
from annotator.validation.base import ValidationIssue, ValidationRule


def _shoelace_area(points: list) -> float:
    n = len(points)
    if n < 3:
        return 0.0
    area = 0.0
    for i in range(n):
        j = (i + 1) % n
        area += points[i][0] * points[j][1]
        area -= points[j][0] * points[i][1]
    return abs(area) / 2.0


class SmallPolygonRule(ValidationRule):
    name = "SmallPolygon"

    def __init__(self, min_area: float = 0.001):
        self.min_area = min_area

    def check(self, project, all_annotations):
        issues = []
        for img_path, anns in all_annotations.items():
            for ann in anns:
                if ann.ann_type != AnnotationType.SEGMENT:
                    continue
                pts = ann.data.get("points", [])
                area = _shoelace_area(pts)
                if area < self.min_area:
                    issues.append(ValidationIssue(
                        rule_name=self.name,
                        severity="warning",
                        image_path=img_path,
                        ann_id=ann.id,
                        message=f"Polygon area {area:.5f} < threshold {self.min_area}",
                    ))
        return issues
