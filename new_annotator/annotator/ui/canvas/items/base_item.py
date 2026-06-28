from abc import abstractmethod
from PyQt6.QtCore import Qt, QPointF
from PyQt6.QtGui import QColor, QFont, QPen
from PyQt6.QtWidgets import QGraphicsItem

_LABEL_FONT = QFont()
_LABEL_FONT.setPixelSize(12)
_LABEL_FONT.setBold(True)


def _cpen(color, width: float, style=None) -> QPen:
    """Return a cosmetic pen — constant screen-pixel width regardless of zoom/image size."""
    p = QPen(color, width, style or Qt.PenStyle.SolidLine)
    p.setCosmetic(True)
    return p


def _draw_label(painter, scene_pos: QPointF, text: str, color) -> None:
    """Draw text at a fixed 12px screen size, independent of zoom and image resolution."""
    screen_pos = painter.worldTransform().map(scene_pos)
    painter.save()
    painter.resetTransform()
    painter.setFont(_LABEL_FONT)
    painter.setPen(QPen(QColor(0, 0, 0, 180)))
    painter.drawText(screen_pos + QPointF(1, 1), text)
    painter.setPen(QPen(QColor(color)))
    painter.drawText(screen_pos, text)
    painter.restore()


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
