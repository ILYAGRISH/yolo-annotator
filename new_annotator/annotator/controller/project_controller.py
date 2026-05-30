"""
ProjectController — single source of truth for the current session.

Sits between UI and domain:
  UI → controller.add_annotation(ann)
       → pushes AddAnnotationCmd onto QUndoStack
       → cmd.redo() calls controller._raw_add(ann)
       → annotations_changed signal
       → Scene + panels rebuild from controller.current_annotations
"""
import copy
import json
import uuid
from pathlib import Path

from PyQt6.QtCore import QObject, pyqtSignal

try:
    from PyQt6.QtGui import QUndoStack
except ImportError:
    from PyQt6.QtWidgets import QUndoStack  # type: ignore[no-redef]

from annotator.domain.annotation import Annotation
from annotator.domain.class_schema import SCHEMA_VERSION, ClassSchema
from annotator.domain.label_class import LabelClass
from annotator.domain.project import Project
from annotator.storage.project_store import ProjectStore
from annotator.ui.undo.commands import (AddAnnotationCmd, DeleteAnnotationCmd,
                                        UpdateAnnotationCmd)

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".webp"}


class ProjectController(QObject):
    project_changed = pyqtSignal(object)        # Project
    image_changed = pyqtSignal(str, list)        # image_path, [Annotation]
    annotations_changed = pyqtSignal(list)       # [Annotation] for current image
    annotation_selected = pyqtSignal(str)        # ann.id  (empty string = none)
    status_message = pyqtSignal(str)             # human-readable status line

    def __init__(self, parent=None):
        super().__init__(parent)
        self._project: Project | None = None
        self._current_image: str | None = None
        self._annotations: list[Annotation] = []
        self._undo_stack = QUndoStack(self)
        self._dirty_images: set[str] = set()

    # ── read-only properties ──────────────────────────────────────────────────

    @property
    def project(self) -> Project | None:
        return self._project

    @property
    def current_image(self) -> str | None:
        return self._current_image

    @property
    def current_annotations(self) -> list[Annotation]:
        return list(self._annotations)

    @property
    def undo_stack(self) -> QUndoStack:
        return self._undo_stack

    # ── project management ────────────────────────────────────────────────────

    def create_project(self, name: str, project_dir: Path) -> Project:
        self._flush_current_image()
        project = Project.create(name)
        ProjectStore.save(project, project_dir)
        self._activate_project(project)
        self.status_message.emit(f"Created project: {project_dir}")
        return project

    def open_project(self, project_dir: Path) -> Project:
        self._flush_current_image()
        project = ProjectStore.load(project_dir)
        self._activate_project(project)
        self.status_message.emit(f"Opened: {project_dir}")
        return project

    def save_project(self):
        if not self._project or not self._project.project_path:
            return
        self._flush_current_image()
        ProjectStore.save(self._project, self._project.project_path)
        self._dirty_images.clear()
        self.status_message.emit(f"Saved: {self._project.project_path}")

    def _activate_project(self, project: Project):
        self._project = project
        self._current_image = None
        self._annotations = []
        self._undo_stack.clear()
        self._dirty_images.clear()
        self.project_changed.emit(project)

    # ── image management ──────────────────────────────────────────────────────

    def add_images_from_folder(self, folder: Path) -> int:
        if not self._project:
            return 0
        added = 0
        for p in sorted(folder.iterdir()):
            if p.suffix.lower() in IMAGE_EXTS:
                self._project.add_image(str(p))
                added += 1
        if added:
            self._project.settings.image_folder = str(folder)
            if self._project.project_path:
                ProjectStore.save(self._project, self._project.project_path)
            self.project_changed.emit(self._project)
            self.status_message.emit(f"Added {added} images from {folder}")
        return added

    def set_image(self, image_path: str):
        if image_path == self._current_image:
            return
        self._flush_current_image()
        self._current_image = image_path
        self._annotations = []
        if self._project and self._project.project_path:
            self._annotations = ProjectStore.load_annotations(
                self._project, image_path)
        self._undo_stack.clear()
        self.image_changed.emit(image_path, list(self._annotations))
        self.annotations_changed.emit(list(self._annotations))

    def _flush_current_image(self):
        if not self._current_image or not self._project:
            return
        if self._current_image not in self._dirty_images:
            return
        if self._project.project_path:
            ProjectStore.save_annotations(
                self._project, self._current_image, self._annotations)
            self._export_yolo(self._current_image, self._annotations)
        self._dirty_images.discard(self._current_image)

    def _export_yolo(self, image_path: str, annotations: list):
        try:
            from annotator.exporters.yolo_seg import YoloSegExporter
            out = YoloSegExporter.export_image(image_path, annotations, self._project)
            self.status_message.emit(
                f"Saved  ·  YOLO: {out.parent.name}/{out.name}")
        except Exception as exc:
            self.status_message.emit(f"YOLO export warning: {exc}")

    # ── annotation CRUD (through undo stack) ──────────────────────────────────

    def add_annotation(self, ann: Annotation):
        if not self._current_image:
            return
        self._undo_stack.push(AddAnnotationCmd(self, ann))

    def delete_annotation(self, ann_id: str):
        ann = self.get_annotation(ann_id)
        if ann:
            self._undo_stack.push(DeleteAnnotationCmd(self, ann))

    def update_annotation_data(self, ann_id: str, new_data: dict,
                                text: str = "Edit annotation"):
        ann = self.get_annotation(ann_id)
        if ann:
            self._undo_stack.push(
                UpdateAnnotationCmd(self, ann_id, ann.data, new_data, text))

    def select_annotation(self, ann_id: str):
        self.annotation_selected.emit(ann_id)

    def get_annotation(self, ann_id: str) -> Annotation | None:
        return next((a for a in self._annotations if a.id == ann_id), None)

    # ── raw operations (called ONLY by undo commands) ─────────────────────────

    def _raw_add(self, ann: Annotation):
        self._annotations.append(ann)
        self._mark_dirty()
        self.annotations_changed.emit(list(self._annotations))

    def _raw_delete(self, ann_id: str):
        self._annotations = [a for a in self._annotations if a.id != ann_id]
        self._mark_dirty()
        self.annotations_changed.emit(list(self._annotations))

    def _raw_update(self, ann_id: str, data: dict):
        for ann in self._annotations:
            if ann.id == ann_id:
                ann.data = copy.deepcopy(data)
                break
        self._mark_dirty()
        self.annotations_changed.emit(list(self._annotations))

    def _mark_dirty(self):
        if self._current_image:
            self._dirty_images.add(self._current_image)

    # ── class schema management ───────────────────────────────────────────────

    def count_annotations_for_class(self, class_id: int) -> int:
        """Count annotations referencing class_id across all saved images."""
        if not self._project:
            return 0
        total = 0
        # Include the currently loaded (possibly unsaved) annotations
        current_counted = False
        all_anns = ProjectStore.load_all_annotations(self._project)
        for img_path, anns in all_anns.items():
            if img_path == self._current_image:
                current_counted = True
                anns = self._annotations  # use in-memory version
            total += sum(1 for a in anns if a.class_id == class_id)
        if not current_counted:
            total += sum(1 for a in self._annotations if a.class_id == class_id)
        return total

    def update_class(self, updated: LabelClass) -> None:
        """Replace a class in the schema. Fires project_changed."""
        if not self._project:
            return
        for i, c in enumerate(self._project.classes):
            if c.id == updated.id:
                self._project.classes[i] = updated
                break
        self.save_project()
        self.project_changed.emit(self._project)

    def add_class(self, name: str, color: str | None = None) -> LabelClass:
        if not self._project:
            raise RuntimeError("No project open")
        lc = self._project.add_class(name, color)
        self.save_project()
        self.project_changed.emit(self._project)
        return lc

    def reorder_classes(self, new_order: list[int]) -> None:
        """Re-order classes by their IDs."""
        if not self._project:
            return
        id_map = {c.id: c for c in self._project.classes}
        self._project.classes = [id_map[cid] for cid in new_order if cid in id_map]
        self.save_project()
        self.project_changed.emit(self._project)

    def delete_class(self, class_id: int, reassign_to: int | None = None) -> None:
        """Delete a class. If reassign_to is not None, re-assign its annotations."""
        if not self._project:
            return
        self._flush_current_image()

        all_anns = ProjectStore.load_all_annotations(self._project)
        modified: dict[str, list[Annotation]] = {}
        for img_path, anns in all_anns.items():
            new_anns: list[Annotation] = []
            changed = False
            for a in anns:
                if a.class_id == class_id:
                    changed = True
                    if reassign_to is not None:
                        a2 = copy.deepcopy(a)
                        a2.class_id = reassign_to
                        new_anns.append(a2)
                    # else: drop the annotation
                else:
                    new_anns.append(a)
            if changed:
                modified[img_path] = new_anns

        ProjectStore.save_all_annotations(self._project, modified)

        # Update in-memory annotations for current image
        if self._current_image in modified:
            self._annotations = modified[self._current_image]
            self.annotations_changed.emit(list(self._annotations))

        self._project.remove_class(class_id)
        self.save_project()
        self.project_changed.emit(self._project)

    def export_class_schema(self, dest_path: Path) -> None:
        """Write class_schema.json to an arbitrary path."""
        if not self._project:
            return
        schema = ClassSchema(schema_version=SCHEMA_VERSION, classes=self._project.classes)
        with open(dest_path, "w", encoding="utf-8") as f:
            json.dump(schema.to_dict(), f, indent=2, ensure_ascii=False)
        self.status_message.emit(f"Schema exported: {dest_path}")

    def import_class_schema(self, src_path: Path) -> list[dict]:
        """
        Load a class_schema.json and return a conflict report.

        Each entry: {"incoming": LabelClass, "conflict_type": "name"|"id"|None,
                     "existing": LabelClass|None}
        The caller resolves conflicts and then calls apply_import_schema().
        """
        if not self._project:
            return []
        with open(src_path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        schema = ClassSchema.from_dict(raw)
        existing_by_id = {c.id: c for c in self._project.classes}
        existing_by_name = {c.name.lower(): c for c in self._project.classes}
        report = []
        for inc in schema.classes:
            conflict_type = None
            existing = None
            if inc.id in existing_by_id:
                conflict_type = "id"
                existing = existing_by_id[inc.id]
            elif inc.name.lower() in existing_by_name:
                conflict_type = "name"
                existing = existing_by_name[inc.name.lower()]
            report.append({
                "incoming": inc,
                "conflict_type": conflict_type,
                "existing": existing,
            })
        return report

    # ── validation ────────────────────────────────────────────────────────────

    def run_validation(self):
        """Run all validation rules against the full dataset. Returns ValidationReport."""
        if not self._project:
            raise RuntimeError("No project open")
        from annotator.validation.validator import Validator
        all_anns = ProjectStore.load_all_annotations(self._project)
        # Overlay in-memory annotations for the currently open image
        if self._current_image:
            all_anns[self._current_image] = self._annotations
        # Ensure every registered image is present (so EmptyImageRule sees them)
        for img in self._project.images:
            all_anns.setdefault(img.path, [])
        return Validator().run(self._project, all_anns)

    # ── dataset export ────────────────────────────────────────────────────────

    def get_type_mismatches(self) -> list[str]:
        """Return unique descriptions where ann.ann_type.value != class.annotation_type."""
        if not self._project:
            return []
        all_anns = ProjectStore.load_all_annotations(self._project)
        if self._current_image:
            all_anns[self._current_image] = self._annotations
        seen: set[tuple] = set()
        mismatches: list[str] = []
        for anns in all_anns.values():
            for ann in anns:
                cls = self._project.get_class(ann.class_id)
                if cls and cls.annotation_type != ann.ann_type.value:
                    key = (cls.name, cls.annotation_type, ann.ann_type.value)
                    if key not in seen:
                        seen.add(key)
                        mismatches.append(
                            f'"{cls.name}": schema={cls.annotation_type},'
                            f' actual={ann.ann_type.value}')
        return mismatches

    def get_annotation_type_counts(self) -> dict[str, int]:
        """Return {type_str: count} across all saved + in-memory annotations."""
        if not self._project:
            return {}
        all_anns = ProjectStore.load_all_annotations(self._project)
        if self._current_image:
            all_anns[self._current_image] = self._annotations
        counts: dict[str, int] = {}
        for anns in all_anns.values():
            for ann in anns:
                t = ann.ann_type.value
                counts[t] = counts.get(t, 0) + 1
        return counts

    def export_dataset(self, output_dir: Path,
                       format_name: str,
                       copy_images: bool = True) -> None:
        """Export the full dataset in the requested YOLO format."""
        if not self._project:
            raise RuntimeError("No project open")
        self._flush_current_image()

        all_anns = ProjectStore.load_all_annotations(self._project)
        if self._current_image:
            all_anns[self._current_image] = self._annotations
        for img in self._project.images:
            all_anns.setdefault(img.path, [])

        if format_name == "yolo_detect":
            from annotator.exporters.yolo_detect import YoloDetectExporter
            exp = YoloDetectExporter()
        elif format_name == "yolo_seg":
            from annotator.exporters.yolo_seg import YoloSegExporter
            exp = YoloSegExporter()
        elif format_name == "yolo_obb":
            from annotator.exporters.yolo_obb import YoloObbExporter
            exp = YoloObbExporter()
        elif format_name == "yolo_pose":
            from annotator.exporters.yolo_pose import YoloPoseExporter
            exp = YoloPoseExporter()
        elif format_name == "yolo_classify":
            from annotator.exporters.yolo_classify import YoloClassifyExporter
            exp = YoloClassifyExporter()
        elif format_name == "coco":
            from annotator.exporters.coco import CocoExporter
            exp = CocoExporter()
        else:
            raise ValueError(f"Unknown export format: {format_name!r}")

        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        exp.export(self._project, output_dir,
                   all_annotations=all_anns, copy_images=copy_images)
        self.status_message.emit(f"Exported [{exp.name}] → {output_dir}")

    def export_validation_report(self, path: Path, fmt: str = "json") -> None:
        from annotator.validation.validator import Validator
        report = self.run_validation()
        name = self._project.name if self._project else ""
        if fmt == "csv":
            Validator.export_csv(report, path)
        else:
            Validator.export_json(report, path, name)
        self.status_message.emit(f"Report exported: {path}")

    def apply_import_schema(self, resolved: list[LabelClass],
                            remap: dict[int, int]) -> None:
        """
        Apply resolved classes after import.

        resolved  — list of LabelClass objects to add/replace.
        remap     — {old_id → new_id} for ID conflicts that were auto-remapped.
                    All annotation files are rewritten with the new IDs.
        """
        if not self._project:
            return
        self._flush_current_image()

        # Apply ID remap to all annotation files
        if remap:
            all_anns = ProjectStore.load_all_annotations(self._project)
            remapped: dict[str, list[Annotation]] = {}
            for img_path, anns in all_anns.items():
                new_anns = []
                changed = False
                for a in anns:
                    if a.class_id in remap:
                        a2 = copy.deepcopy(a)
                        a2.class_id = remap[a.class_id]
                        new_anns.append(a2)
                        changed = True
                    else:
                        new_anns.append(a)
                if changed:
                    remapped[img_path] = new_anns
            ProjectStore.save_all_annotations(self._project, remapped)
            # Update in-memory if needed
            if self._current_image in remapped:
                self._annotations = remapped[self._current_image]
                self.annotations_changed.emit(list(self._annotations))

        # Merge resolved classes into project
        existing_ids = {c.id for c in self._project.classes}
        for lc in resolved:
            if lc.id in existing_ids:
                # Replace existing
                for i, c in enumerate(self._project.classes):
                    if c.id == lc.id:
                        self._project.classes[i] = lc
                        break
            else:
                self._project.classes.append(lc)

        self.save_project()
        self.project_changed.emit(self._project)
        self.status_message.emit(f"Imported {len(resolved)} classes")
