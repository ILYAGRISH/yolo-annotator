from __future__ import annotations
import uuid
from dataclasses import dataclass, field
from typing import Any

ANNOTATION_TYPES = ["bbox", "polygon", "polyline", "obb", "keypoints", "point", "classification"]

# Drawing tools compatible with each annotation_type (enforced in UI and toolbar)
ANNOTATION_TYPE_TOOLS: dict[str, list[str]] = {
    "bbox":           ["bbox"],
    "polygon":        ["polygon", "crack_tool"],
    "polyline":       ["polyline"],
    "obb":            ["obb"],
    "keypoints":      ["pose"],
    "point":          ["point"],
    "classification": [],
}

# Default tool to auto-activate when a class of this type is selected
ANNOTATION_TYPE_DEFAULT_TOOL: dict[str, str | None] = {
    "bbox":           "bbox",
    "polygon":        "polygon",
    "polyline":       "polyline",
    "obb":            "obb",
    "keypoints":      "pose",
    "point":          "point",
    "classification": None,   # no drawing tool
}

@dataclass
class SkeletonKeypoint:
    """One keypoint in a pose skeleton. edges = indices of adjacent keypoints."""
    name: str
    edges: list[int] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"name": self.name, "edges": list(self.edges)}

    @classmethod
    def from_dict(cls, d: dict) -> "SkeletonKeypoint":
        return cls(name=d["name"], edges=list(d.get("edges", [])))


_COLORS = [
    "#FF4444", "#44DD44", "#4488FF", "#FFDD00",
    "#FF44FF", "#00DDDD", "#FF8800", "#8844FF",
    "#44FF99", "#FF4499", "#99FF44", "#4499FF",
]


@dataclass
class ClassAttribute:
    id: str
    name: str
    attr_type: str          # "select" | "text" | "number" | "bool"
    options: list[str] = field(default_factory=list)
    default_value: Any = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "attr_type": self.attr_type,
            "options": self.options,
            "default_value": self.default_value,
        }

    @classmethod
    def from_dict(cls, d: dict) -> ClassAttribute:
        return cls(
            id=d.get("id", str(uuid.uuid4())),
            name=d["name"],
            attr_type=d.get("attr_type", "text"),
            options=d.get("options", []),
            default_value=d.get("default_value"),
        )


@dataclass
class DisplayStyle:
    opacity: float = 0.3
    line_width: int = 2
    fill_color: str | None = None   # None = use class color

    def to_dict(self) -> dict:
        return {
            "opacity": self.opacity,
            "line_width": self.line_width,
            "fill_color": self.fill_color,
        }

    @classmethod
    def from_dict(cls, d: dict) -> DisplayStyle:
        return cls(
            opacity=float(d.get("opacity", 0.3)),
            line_width=int(d.get("line_width", 2)),
            fill_color=d.get("fill_color"),
        )


@dataclass
class LabelClass:
    id: int
    name: str
    color: str                  # hex, e.g. "#FF4444"
    annotation_type: str = "bbox"   # one of ANNOTATION_TYPES
    allowed_tools: list[str] = field(default_factory=list)
    subclasses: list[str] = field(default_factory=list)
    attributes: list[ClassAttribute] = field(default_factory=list)
    display_style: DisplayStyle = field(default_factory=DisplayStyle)
    skeleton: list[SkeletonKeypoint] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "color": self.color,
            "annotation_type": self.annotation_type,
            "allowed_tools": self.allowed_tools,
            "subclasses": self.subclasses,
            "attributes": [a.to_dict() for a in self.attributes],
            "display_style": self.display_style.to_dict(),
            "skeleton": [kp.to_dict() for kp in self.skeleton],
        }

    @classmethod
    def from_dict(cls, d: dict) -> LabelClass:
        ds = d.get("display_style", {})
        return cls(
            id=d["id"],
            name=d["name"],
            color=d.get("color", "#AAAAAA"),
            annotation_type=d.get("annotation_type", "bbox"),
            allowed_tools=d.get("allowed_tools", []),
            subclasses=d.get("subclasses", []),
            attributes=[ClassAttribute.from_dict(a) for a in d.get("attributes", [])],
            display_style=DisplayStyle.from_dict(ds) if ds else DisplayStyle(),
            skeleton=[SkeletonKeypoint.from_dict(k) for k in d.get("skeleton", [])],
        )

    @staticmethod
    def default_color(index: int) -> str:
        return _COLORS[index % len(_COLORS)]
