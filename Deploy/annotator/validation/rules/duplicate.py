from annotator.domain.annotation import AnnotationType
from annotator.validation.base import ValidationIssue, ValidationRule


def _bbox(ann) -> tuple[float, float, float, float] | None:
    """Return (x1, y1, x2, y2) bounding box in normalized coords."""
    if ann.ann_type == AnnotationType.BBOX:
        x, y, w, h = ann.data["x"], ann.data["y"], ann.data["w"], ann.data["h"]
        return x, y, x + w, y + h
    if ann.ann_type in (AnnotationType.SEGMENT, AnnotationType.POLYLINE):
        pts = ann.data.get("points", [])
        if not pts:
            return None
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        return min(xs), min(ys), max(xs), max(ys)
    return None


def _iou(a: tuple, b: tuple) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    if ix2 <= ix1 or iy2 <= iy1:
        return 0.0
    inter = (ix2 - ix1) * (iy2 - iy1)
    area_a = (ax2 - ax1) * (ay2 - ay1)
    area_b = (bx2 - bx1) * (by2 - by1)
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


class DuplicateAnnotationRule(ValidationRule):
    name = "DuplicateAnnotation"

    def __init__(self, iou_threshold: float = 0.85):
        self.iou_threshold = iou_threshold

    def check(self, project, all_annotations):
        issues = []
        for img_path, anns in all_annotations.items():
            seen: list[tuple] = []   # (class_id, bbox, ann_id)
            for ann in anns:
                bb = _bbox(ann)
                if bb is None:
                    continue
                for s_class, s_bb, s_id in seen:
                    if s_class == ann.class_id and _iou(bb, s_bb) >= self.iou_threshold:
                        issues.append(ValidationIssue(
                            rule_name=self.name,
                            severity="warning",
                            image_path=img_path,
                            ann_id=ann.id,
                            message=f"Possible duplicate of {s_id[:8]}…",
                        ))
                        break
                seen.append((ann.class_id, bb, ann.id))
        return issues
