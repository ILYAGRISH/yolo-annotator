from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from annotator.domain.annotation import Annotation
    from annotator.domain.project import Project


@dataclass
class ValidationIssue:
    rule_name: str
    severity: str       # "error" | "warning" | "info"
    image_path: str
    ann_id: str         # empty string = image-level issue
    message: str


@dataclass
class ValidationReport:
    issues: list[ValidationIssue] = field(default_factory=list)
    stats: dict = field(default_factory=dict)

    @property
    def error_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "error")

    @property
    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "warning")


class ValidationRule(ABC):
    name: str = "base"

    @abstractmethod
    def check(
        self,
        project: "Project",
        all_annotations: dict[str, list["Annotation"]],
    ) -> list[ValidationIssue]:
        ...
