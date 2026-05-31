"""
Persistence layer for .annproj directory format.

Directory layout:
  my_project.annproj/
  ├── project.json          # metadata, settings  (no classes since v3)
  ├── class_schema.json     # all class definitions (since v3)
  ├── images.json           # image inventory
  └── annotations/
      ├── <image_stem>.json # per-image annotations
      └── ...
"""
import json
from pathlib import Path

from annotator.domain.annotation import Annotation
from annotator.domain.class_schema import SCHEMA_VERSION, ClassSchema
from annotator.domain.label_class import LabelClass
from annotator.domain.project import FORMAT_VERSION, ImageRecord, Project

ANNOTS_DIR = "annotations"
PROJECT_FILE = "project.json"
SCHEMA_FILE = "class_schema.json"
IMAGES_FILE = "images.json"


def _migrate_project(data: dict, from_version: int) -> dict:
    """Upgrade project.json to the current FORMAT_VERSION."""
    if from_version < 2:
        data.setdefault("settings", {})
    # v2 → v3: classes moved to class_schema.json; strip them from project.json
    # The caller (load) extracts them before calling from_dict.
    return data


class ProjectStore:

    @staticmethod
    def save(project: Project, path: Path):
        path.mkdir(parents=True, exist_ok=True)
        (path / ANNOTS_DIR).mkdir(exist_ok=True)
        (path / "masks").mkdir(exist_ok=True)

        # project.json  (no classes)
        with open(path / PROJECT_FILE, "w", encoding="utf-8") as f:
            json.dump(project.to_dict(), f, indent=2, ensure_ascii=False)

        # class_schema.json
        schema = ClassSchema(schema_version=SCHEMA_VERSION, classes=project.classes)
        with open(path / SCHEMA_FILE, "w", encoding="utf-8") as f:
            json.dump(schema.to_dict(), f, indent=2, ensure_ascii=False)

        # images.json
        with open(path / IMAGES_FILE, "w", encoding="utf-8") as f:
            json.dump([r.to_dict() for r in project.images], f,
                      indent=2, ensure_ascii=False)

        project.project_path = path

    @staticmethod
    def load(path: Path) -> Project:
        with open(path / PROJECT_FILE, "r", encoding="utf-8") as f:
            proj_data = json.load(f)

        file_version = proj_data.get("format_version", 1)
        if file_version < FORMAT_VERSION:
            proj_data = _migrate_project(proj_data, file_version)

        # Extract inline classes from old v1/v2 project.json if present
        inline_classes: list[dict] = proj_data.pop("classes", [])

        project = Project.from_dict(proj_data)
        project.project_path = path

        # Load class schema
        schema_file = path / SCHEMA_FILE
        if schema_file.exists():
            with open(schema_file, "r", encoding="utf-8") as f:
                schema = ClassSchema.from_dict(json.load(f))
            project.classes = schema.classes
        elif inline_classes:
            # Migrate inline classes from old project.json
            project.classes = [LabelClass.from_dict(c) for c in inline_classes]
        # else: no classes at all (empty project)

        # images.json
        images_file = path / IMAGES_FILE
        if images_file.exists():
            with open(images_file, "r", encoding="utf-8") as f:
                project.images = [ImageRecord.from_dict(r) for r in json.load(f)]

        return project

    @staticmethod
    def load_annotations(project: Project, image_path: str) -> list[Annotation]:
        if project.project_path is None:
            return []
        stem = Path(image_path).stem
        ann_file = project.project_path / ANNOTS_DIR / f"{stem}.json"
        if not ann_file.exists():
            return []
        with open(ann_file, "r", encoding="utf-8") as f:
            return [Annotation.from_dict(d) for d in json.load(f)]

    @staticmethod
    def save_annotations(project: Project, image_path: str, annotations: list[Annotation]):
        if project.project_path is None:
            return
        ann_dir = project.project_path / ANNOTS_DIR
        ann_dir.mkdir(exist_ok=True)
        stem = Path(image_path).stem
        with open(ann_dir / f"{stem}.json", "w", encoding="utf-8") as f:
            json.dump([a.to_dict() for a in annotations], f,
                      indent=2, ensure_ascii=False)

    @staticmethod
    def load_all_annotations(project: Project) -> dict[str, list[Annotation]]:
        """Load all per-image annotation files. Returns {image_path: [Annotation]}."""
        result: dict[str, list[Annotation]] = {}
        if project.project_path is None:
            return result
        ann_dir = project.project_path / ANNOTS_DIR
        if not ann_dir.exists():
            return result
        stem_to_path = {Path(img.path).stem: img.path for img in project.images}
        for ann_file in ann_dir.glob("*.json"):
            img_path = stem_to_path.get(ann_file.stem)
            if img_path is None:
                continue
            with open(ann_file, "r", encoding="utf-8") as f:
                result[img_path] = [Annotation.from_dict(d) for d in json.load(f)]
        return result

    @staticmethod
    def save_all_annotations(project: Project, all_annotations: dict[str, list[Annotation]]):
        """Overwrite annotation files for all images in the dict."""
        for img_path, anns in all_annotations.items():
            ProjectStore.save_annotations(project, img_path, anns)
