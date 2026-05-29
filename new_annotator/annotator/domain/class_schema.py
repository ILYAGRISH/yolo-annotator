from __future__ import annotations
from dataclasses import dataclass, field

from annotator.domain.label_class import LabelClass

SCHEMA_VERSION = 1


@dataclass
class ClassSchema:
    schema_version: int
    classes: list[LabelClass] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "classes": [c.to_dict() for c in self.classes],
        }

    @classmethod
    def from_dict(cls, d: dict) -> ClassSchema:
        d = cls._migrate(d)
        return cls(
            schema_version=d["schema_version"],
            classes=[LabelClass.from_dict(c) for c in d.get("classes", [])],
        )

    @classmethod
    def _migrate(cls, d: dict) -> dict:
        version = d.get("schema_version", 0)
        if version < 1:
            # v0: raw list of class dicts (old project.json inline format)
            if isinstance(d, list):
                d = {"schema_version": 1, "classes": d}
            else:
                d.setdefault("schema_version", 1)
        return d

    @classmethod
    def empty(cls) -> ClassSchema:
        return cls(schema_version=SCHEMA_VERSION)
