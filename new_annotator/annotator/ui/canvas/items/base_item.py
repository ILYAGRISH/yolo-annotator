from abc import abstractmethod
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPen
from PyQt6.QtWidgets import QGraphicsItem


def _cpen(color, width: float, style=None) -> QPen:
    """Return a cosmetic pen — constant screen-pixel width regardless of zoom/image size."""
    p = QPen(color, width, style or Qt.PenStyle.SolidLine)
    p.setCosmetic(True)
    return p


class BaseAnnotationItem(QGraphicsItem):
    """
    Base for all annotation graphics items.
    Concrete subclasses: PolygonAnnotationItem, BBoxAnnotationItem, etc.
    """

    def __init__(self, annotation_id: str, class_color: str, parent=None):
        super().__init__(parent)
        self.annotation_id = annotation_id
        self.class_color = class_color
        self.line_width: float = 2.0
        self.fill_opacity: float = 0.3
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)

    @abstractmethod
    def update_from_data(self, data: dict, image_size: tuple[int, int]):
        """Rebuild geometry from normalized annotation data."""

    @abstractmethod
    def to_data(self, image_size: tuple[int, int]) -> dict:
        """Export current geometry back to normalized annotation data dict."""
