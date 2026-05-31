from dataclasses import dataclass


@dataclass
class ExportJob:
    """Parameters for one task in a multi-task export."""
    format_name: str           # "yolo_detect" | "yolo_seg"
    geometry_policy: str = "skip"  # "skip" | "convert"
