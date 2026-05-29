import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class AnnotationType(Enum):
    SEGMENT = "segment"    # closed polygon — segmentation mask
    POLYLINE = "polyline"  # open polyline — roads, cracks, contours
    BBOX = "bbox"          # axis-aligned bounding box
    OBB = "obb"            # oriented bounding box (Phase 3)
    POSE = "pose"          # keypoint skeleton (Phase 3)
    CLASSIFY = "classify"  # image-level label (Phase 3)


@dataclass
class Annotation:
    """
    Format-independent annotation.
    All geometry lives in `data` as normalized [0,1] coordinates.

    data schemas by type:
      SEGMENT  → {"points": [[x,y], ...]}          closed polygon
      POLYLINE → {"points": [[x,y], ...]}          open polyline
      BBOX     → {"x", "y", "w", "h": float}       top-left + size, normalized
      OBB      → {"cx","cy","w","h","angle_deg"}
      POSE     → {"keypoints": [[x,y,vis], ...]}
    """
    id: str
    class_id: int
    ann_type: AnnotationType
    data: dict
    meta: dict = field(default_factory=dict)

    @classmethod
    def new(cls, class_id: int, ann_type: AnnotationType, data: dict,
            tool: str = "manual") -> "Annotation":
        now = datetime.utcnow().isoformat()
        return cls(
            id=str(uuid.uuid4()),
            class_id=class_id,
            ann_type=ann_type,
            data=data,
            meta={"created_at": now, "modified_at": now, "tool": tool, "source": "manual"},
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "class_id": self.class_id,
            "type": self.ann_type.value,
            "data": self.data,
            "meta": self.meta,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Annotation":
        return cls(
            id=d["id"],
            class_id=d["class_id"],
            ann_type=AnnotationType(d["type"]),
            data=d["data"],
            meta=d.get("meta", {}),
        )
