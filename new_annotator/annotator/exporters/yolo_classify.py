"""YOLO Classify exporter — image-level classification folder structure.

Output:
  output_dir/
    train/
      class_name_A/  image1.jpg  image2.jpg
      class_name_B/  image3.jpg
    val/
      ...
"""
import shutil
from pathlib import Path

from annotator.domain.annotation import AnnotationType
from annotator.exporters.base import BaseExporter


class YoloClassifyExporter(BaseExporter):

    @property
    def name(self) -> str:
        return "YOLO Classify"

    @property
    def file_extension(self) -> str:
        return ""

    def export(self, project, output_dir: Path, **kwargs):
        all_annotations = kwargs.get("all_annotations", {})
        output_dir = Path(output_dir)

        exported = 0
        for img_rec in project.images:
            split = img_rec.split or "train"
            img_path = Path(img_rec.path)
            anns = all_annotations.get(img_rec.path, [])

            classify_anns = [a for a in anns if a.ann_type == AnnotationType.CLASSIFY]
            for ann in classify_anns:
                cls = project.get_class(ann.class_id)
                if cls is None:
                    continue
                class_dir = output_dir / split / cls.name
                class_dir.mkdir(parents=True, exist_ok=True)
                if img_path.exists():
                    shutil.copy2(img_path, class_dir / img_path.name)
                    exported += 1
