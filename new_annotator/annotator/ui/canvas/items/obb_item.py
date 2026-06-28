"""OBBAnnotationItem — oriented bounding box with corner + rotation handles.

Handle indices:
  0 — rotation handle (circle above top-center, rotates with the box)
  1 — TL corner
  2 — TR corner
  3 — BR corner
  4 — BL corner

Angle convention: clockwise in screen coordinates (Y-axis points down).
  angle=0   → box is axis-aligned, rotation handle is directly above.
  angle=90  → box is rotated 90° clockwise, handle is to the right.
"""
import math

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QBrush, QColor, QPainter, QPainterPath, QPen

from annotator.ui.canvas.items.base_item import BaseAnnotationItem, _cpen, _draw_label

HANDLE_SCREEN_R = 5.0
HANDLE_HIT = 9.0
ROTATION_OFFSET = 22.0   # pixels from top edge to rotation handle center
_BOUNDING_MARGIN = 30.0


def _rotate(px: float, py: float, cx: float, cy: float, angle_deg: float):
    """Rotate (px, py) clockwise around (cx, cy) by angle_deg (screen coords)."""
    rad = math.radians(angle_deg)
    cos_a, sin_a = math.cos(rad), math.sin(rad)
    dx, dy = px - cx, py - cy
    return (cx + cos_a * dx - sin_a * dy,
            cy + sin_a * dx + cos_a * dy)


class OBBAnnotationItem(BaseAnnotationItem):

    def __init__(self, annotation_id: str,
                 cx: float, cy: float, w: float, h: float, angle_deg: float,
                 class_color: str, label: str = "", parent=None):
        super().__init__(annotation_id, class_color, parent)
        self._cx = cx
        self._cy = cy
        self._w = w
        self._h = h
        self._angle = angle_deg
        self.label = label
        self._hover_handle = -1
        self._lod: float = 1.0
        self.setAcceptHoverEvents(True)

    # ── geometry helpers ──────────────────────────────────────────────────────

    def _corners(self) -> list[tuple[float, float]]:
        """Scene-space corners: TL, TR, BR, BL (clockwise)."""
        hw, hh = self._w / 2, self._h / 2
        return [
            _rotate(self._cx - hw, self._cy - hh, self._cx, self._cy, self._angle),
            _rotate(self._cx + hw, self._cy - hh, self._cx, self._cy, self._angle),
            _rotate(self._cx + hw, self._cy + hh, self._cx, self._cy, self._angle),
            _rotate(self._cx - hw, self._cy + hh, self._cx, self._cy, self._angle),
        ]

    def _rot_handle_pos(self) -> tuple[float, float]:
        """Scene position of the rotation handle (above top edge)."""
        r = self._h / 2 + ROTATION_OFFSET
        rad = math.radians(self._angle)
        return (self._cx + r * math.sin(rad),
                self._cy - r * math.cos(rad))

    # ── handle API (used by SelectTool) ───────────────────────────────────────

    def handle_at(self, pos: QPointF) -> int:
        hit_r = max(HANDLE_HIT, HANDLE_SCREEN_R * 1.5 / max(self._lod, 0.05))
        rx, ry = self._rot_handle_pos()
        if (QPointF(rx, ry) - pos).manhattanLength() <= hit_r:
            return 0
        for i, (cx, cy) in enumerate(self._corners()):
            if (QPointF(cx, cy) - pos).manhattanLength() <= hit_r:
                return i + 1
        return -1

    def move_handle(self, index: int, new_pos: QPointF):
        self.prepareGeometryChange()
        if index == 0:
            # Rotation: compute clockwise angle from center to cursor
            dx = new_pos.x() - self._cx
            dy = new_pos.y() - self._cy
            self._angle = math.degrees(math.atan2(dx, -dy))
        else:
            # Corner resize (opposite corner stays fixed)
            corner_idx = index - 1        # 0=TL,1=TR,2=BR,3=BL
            opp_idx = (corner_idx + 2) % 4
            opp = self._corners()[opp_idx]
            # New center = midpoint(new corner, fixed opposite corner)
            new_cx = (new_pos.x() + opp[0]) / 2
            new_cy = (new_pos.y() + opp[1]) / 2
            # Displacement to new corner in OBB-local frame (rotate by -angle)
            d = QPointF(new_pos.x() - new_cx, new_pos.y() - new_cy)
            rad = math.radians(self._angle)
            cos_a, sin_a = math.cos(rad), math.sin(rad)
            dx_local = cos_a * d.x() + sin_a * d.y()
            dy_local = -sin_a * d.x() + cos_a * d.y()
            self._cx, self._cy = new_cx, new_cy
            self._w = max(4.0, 2 * abs(dx_local))
            self._h = max(4.0, 2 * abs(dy_local))
        self.update()

    # ── BaseAnnotationItem interface ──────────────────────────────────────────

    def update_from_data(self, data: dict, image_size: tuple[int, int]):
        iw, ih = image_size
        self.prepareGeometryChange()
        self._cx = data["cx"] * iw
        self._cy = data["cy"] * ih
        self._w = data["w"] * iw
        self._h = data["h"] * ih
        self._angle = data.get("angle_deg", 0.0)
        self.update()

    def to_data(self, image_size: tuple[int, int]) -> dict:
        iw, ih = image_size
        return {
            "cx": self._cx / iw,
            "cy": self._cy / ih,
            "w": self._w / iw,
            "h": self._h / ih,
            "angle_deg": self._angle,
        }

    # ── QGraphicsItem overrides ───────────────────────────────────────────────

    def boundingRect(self) -> QRectF:
        pts = list(self._corners())
        pts.append(self._rot_handle_pos())
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        m = _BOUNDING_MARGIN
        return QRectF(min(xs) - m, min(ys) - m,
                      max(xs) - min(xs) + 2 * m, max(ys) - min(ys) + 2 * m)

    def shape(self) -> QPainterPath:
        corners = self._corners()
        path = QPainterPath()
        path.moveTo(*corners[0])
        for pt in corners[1:]:
            path.lineTo(*pt)
        path.closeSubpath()
        return path

    def paint(self, painter: QPainter, option, widget=None):
        self._lod = option.levelOfDetailFromTransform(painter.worldTransform())
        handle_r = HANDLE_SCREEN_R / self._lod

        selected = self.isSelected()
        color = QColor(self.class_color)
        corners = self._corners()

        path = QPainterPath()
        path.moveTo(*corners[0])
        for pt in corners[1:]:
            path.lineTo(*pt)
        path.closeSubpath()

        alpha = int(min(255, self.fill_opacity * 255 * (1.5 if selected else 1.0)))
        fill = QColor(color)
        fill.setAlpha(alpha)
        lw = self.line_width + (1.0 if selected else 0.0)

        painter.setBrush(QBrush(fill))
        painter.setPen(_cpen(color, lw))
        painter.drawPath(path)

        if selected:
            # Dashed line from top-center to rotation handle
            tc = QPointF((corners[0][0] + corners[1][0]) / 2,
                         (corners[0][1] + corners[1][1]) / 2)
            rx, ry = self._rot_handle_pos()
            painter.setPen(_cpen(color, 1, Qt.PenStyle.DashLine))
            painter.drawLine(tc, QPointF(rx, ry))

            # Rotation handle (orange circle)
            painter.setBrush(QBrush(QColor(255, 170, 0)))
            painter.setPen(_cpen(Qt.GlobalColor.black, 1))
            painter.drawEllipse(QPointF(rx, ry), handle_r, handle_r)

            # Corner handles
            for i, (cx, cy) in enumerate(corners):
                if i + 1 == self._hover_handle:
                    painter.setBrush(QBrush(QColor(255, 220, 0)))
                    painter.setPen(_cpen(Qt.GlobalColor.black, 1))
                else:
                    painter.setBrush(QBrush(Qt.GlobalColor.white))
                    painter.setPen(_cpen(color, 1.5))
                painter.drawEllipse(QPointF(cx, cy), handle_r, handle_r)

        if self.label:
            _draw_label(painter, QPointF(corners[0][0] + 4, corners[0][1] - 4), self.label, color)

    def hoverMoveEvent(self, event):
        if self.isSelected():
            idx = self.handle_at(event.pos())
            if idx != self._hover_handle:
                self._hover_handle = idx
                self.update()
        super().hoverMoveEvent(event)

    def hoverLeaveEvent(self, event):
        self._hover_handle = -1
        self.update()
        super().hoverLeaveEvent(event)
