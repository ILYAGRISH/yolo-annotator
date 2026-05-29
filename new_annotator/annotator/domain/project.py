import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from annotator.domain.label_class import LabelClass

FORMAT_VERSION = 3

_DEFAULT_COLORS = [
    "#FF4444", "#44DD44", "#4488FF", "#FFDD00",
    "#FF44FF", "#00DDDD", "#FF8800", "#8844FF",
    "#44FF99", "#FF4499", "#99FF44", "#4499FF",
]


@dataclass
class ImageRecord:
    path: str
    width: int = 0
    height: int = 0
    split: str = "train"

    def to_dict(self) -> dict:
        return {"path": self.path, "width": self.width,
                "height": self.height, "split": self.split}

    @classmethod
    def from_dict(cls, d: dict) -> "ImageRecord":
        return cls(path=d["path"], width=d.get("width", 0),
                   height=d.get("height", 0), split=d.get("split", "train"))


@dataclass
class ProjectSettings:
    default_export_format: str = "yolo_seg"
    autosave_interval_sec: int = 60
    image_folder: str = ""

    def to_dict(self) -> dict:
        return {
            "default_export_format": self.default_export_format,
            "autosave_interval_sec": self.autosave_interval_sec,
            "image_folder": self.image_folder,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ProjectSettings":
        return cls(
            default_export_format=d.get("default_export_format", "yolo_seg"),
            autosave_interval_sec=d.get("autosave_interval_sec", 60),
            image_folder=d.get("image_folder", ""),
        )


@dataclass
class Project:
    id: str
    name: str
    created_at: str
    modified_at: str
    # classes live in class_schema.json; loaded by ProjectStore and placed here at runtime
    classes: list[LabelClass] = field(default_factory=list)
    images: list[ImageRecord] = field(default_factory=list)
    settings: ProjectSettings = field(default_factory=ProjectSettings)

    # Runtime-only
    project_path: Path | None = field(default=None, repr=False)

    @classmethod
    def create(cls, name: str) -> "Project":
        now = datetime.utcnow().isoformat()
        proj = cls(id=str(uuid.uuid4()), name=name,
                   created_at=now, modified_at=now)
        proj.add_class("object")
        return proj

    # ── class management ──────────────────────────────────────────────────────

    def add_class(self, name: str, color: str | None = None) -> LabelClass:
        next_id = max((c.id for c in self.classes), default=-1) + 1
        color = color or _DEFAULT_COLORS[next_id % len(_DEFAULT_COLORS)]
        lc = LabelClass(id=next_id, name=name, color=color)
        self.classes.append(lc)
        return lc

    def remove_class(self, class_id: int):
        self.classes = [c for c in self.classes if c.id != class_id]

    def get_class(self, class_id: int) -> LabelClass | None:
        return next((c for c in self.classes if c.id == class_id), None)

    # ── image management ──────────────────────────────────────────────────────

    def add_image(self, path: str, width: int = 0, height: int = 0) -> ImageRecord:
        if any(r.path == path for r in self.images):
            return next(r for r in self.images if r.path == path)
        rec = ImageRecord(path=path, width=width, height=height)
        self.images.append(rec)
        return rec

    # ── serialization (project.json only — no classes) ────────────────────────

    def to_dict(self) -> dict:
        self.modified_at = datetime.utcnow().isoformat()
        return {
            "format_version": FORMAT_VERSION,
            "id": self.id,
            "name": self.name,
            "created_at": self.created_at,
            "modified_at": self.modified_at,
            "settings": self.settings.to_dict(),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Project":
        return cls(
            id=d["id"],
            name=d["name"],
            created_at=d["created_at"],
            modified_at=d["modified_at"],
            settings=ProjectSettings.from_dict(d.get("settings", {})),
        )
