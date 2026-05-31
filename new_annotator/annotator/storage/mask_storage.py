"""
MaskStorage — save/load binary mask PNGs and convert between bitmap ↔ polygon.

Layout inside .annproj/:
  masks/<image_stem>_<ann_id>.png   binary mask, same resolution as source image
                                     white (255) = object, black (0) = background

mask_png_path stored in annotation.data is always relative to project_path root:
  "masks/img001_<uuid>.png"
"""
from __future__ import annotations

from pathlib import Path


class MaskStorage:

    def __init__(self, project_path: Path):
        self._project_path = Path(project_path)
        self._masks_dir = self._project_path / "masks"
        self._masks_dir.mkdir(exist_ok=True)

    # ── PNG save / load ───────────────────────────────────────────────────────

    def save_mask(self, ann_id: str, image_stem: str, bitmap) -> str:
        """
        Save (H,W) uint8 numpy array as PNG. Returns relative path: "masks/<...>.png".
        """
        import numpy as np
        from PIL import Image

        fname = f"{image_stem}_{ann_id}.png"
        arr = np.asarray(bitmap, dtype=np.uint8)
        Image.fromarray(arr, mode="L").save(self._masks_dir / fname)
        return f"masks/{fname}"

    def load_mask(self, mask_png_path: str):
        """
        Load mask PNG, return (H,W) uint8 numpy array, or None if file missing.
        """
        import numpy as np
        from PIL import Image

        path = self._project_path / mask_png_path
        if not path.exists():
            return None
        return np.array(Image.open(path).convert("L"), dtype=np.uint8)

    # ── bitmap ↔ polygon ──────────────────────────────────────────────────────

    def mask_to_polygon(self, bitmap, image_w: int, image_h: int) -> list[list[float]]:
        """
        Find largest contour in binary mask, return normalized [[x,y],...] polygon.
        Returns [] for empty mask.
        """
        try:
            import cv2
        except ImportError:
            raise ImportError(
                "opencv-python is required for mask contour detection. "
                "Install with: pip install opencv-python")

        import numpy as np
        arr = np.asarray(bitmap, dtype=np.uint8)
        contours, _ = cv2.findContours(
            arr, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return []
        largest = max(contours, key=cv2.contourArea)
        if cv2.contourArea(largest) < 1:
            return []
        perim = cv2.arcLength(largest, True)
        eps = max(1.0, 0.001 * perim)
        approx = cv2.approxPolyDP(largest, eps, True)
        return [[float(pt[0][0]) / image_w, float(pt[0][1]) / image_h]
                for pt in approx]

    def polygon_to_mask(self, polygon: list[list[float]],
                        image_w: int, image_h: int):
        """
        Rasterize normalized polygon to (H,W) uint8 numpy array (255 inside, 0 outside).
        """
        import numpy as np
        try:
            import cv2
        except ImportError:
            raise ImportError(
                "opencv-python is required for mask rasterization. "
                "Install with: pip install opencv-python")

        mask = np.zeros((image_h, image_w), dtype=np.uint8)
        if not polygon:
            return mask
        pts = np.array([[int(x * image_w), int(y * image_h)]
                        for x, y in polygon], dtype=np.int32)
        cv2.fillPoly(mask, [pts], 255)
        return mask

    def mask_to_bbox(self, bitmap, image_w: int, image_h: int) -> list[float]:
        """
        Compute bounding box from non-zero pixels.
        Returns [cx, cy, w, h] normalized, or [] for empty mask.
        """
        import numpy as np
        arr = np.asarray(bitmap, dtype=np.uint8)
        ys, xs = np.nonzero(arr)
        if len(xs) == 0:
            return []
        x1, x2 = int(xs.min()), int(xs.max())
        y1, y2 = int(ys.min()), int(ys.max())
        cx = (x1 + x2) / 2 / image_w
        cy = (y1 + y2) / 2 / image_h
        w = (x2 - x1 + 1) / image_w
        h = (y2 - y1 + 1) / image_h
        return [cx, cy, w, h]
