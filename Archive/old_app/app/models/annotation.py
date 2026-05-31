from dataclasses import dataclass
from enum import Enum


class AnnotationType(Enum):
    SEGMENT = "segment"
    BBOX = "bbox"
    OBB = "obb"
    POSE = "pose"
    CLASSIFY = "classify"


@dataclass
class LabelClass:
    id: int
    name: str
    color: str  # hex, e.g. "#FF4444"


@dataclass
class SegmentAnnotation:
    class_id: int
    points: list  # list of (x, y) tuples, normalized [0, 1]

    def to_yolo(self) -> str:
        coords = " ".join(f"{x:.10f} {y:.10f}" for x, y in self.points)
        return f"{self.class_id} {coords}"

    @classmethod
    def from_yolo_line(cls, line: str) -> "SegmentAnnotation":
        parts = line.strip().split()
        if len(parts) < 5:
            raise ValueError(f"Too few values: {line!r}")
        class_id = int(float(parts[0]))
        coords = list(map(float, parts[1:]))
        if len(coords) % 2 != 0:
            coords = coords[:-1]  # drop orphan coord if file is malformed
        points = [(coords[i], coords[i + 1]) for i in range(0, len(coords), 2)]
        if len(points) < 2:
            raise ValueError("Need at least 2 points")
        return cls(class_id=class_id, points=points)
