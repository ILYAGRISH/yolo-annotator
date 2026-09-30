"""
MaskStorage — save/load binary mask PNGs and convert between bitmap ↔ polygon.

Layout inside .annproj/:
  masks/<image_stem>_<ann_id>.png   binary mask, same resolution as source image
                                     white (255) = object, black (0) = background

  masks/<image_stem>_sem<class_id>_<rev>.png
                                     SEMANTIC layer; a new <rev> is written on
                                     every edit so undo can point back to the
                                     previous (immutable) file

mask_png_path stored in annotation.data is always relative to project_path root:
  "masks/img001_<uuid>.png"
"""
from __future__ import annotations

import uuid
from collections import OrderedDict
from pathlib import Path

# Decoded mask bitmaps keyed by absolute path. Mask files are never rewritten
# in place (every save gets a fresh name), so entries never go stale.
_BITMAP_CACHE: "OrderedDict[str, object]" = OrderedDict()
_BITMAP_CACHE_BUDGET = 256 * 1024 * 1024   # bytes

# Connected regions smaller than this (in pixels) are dropped from polygons.
_MIN_REGION_PX = 4.0


def _cache_put(key: str, arr) -> None:
    _BITMAP_CACHE[key] = arr
    _BITMAP_CACHE.move_to_end(key)
    total = sum(a.nbytes for a in _BITMAP_CACHE.values())
    while total > _BITMAP_CACHE_BUDGET and len(_BITMAP_CACHE) > 1:
        _, old = _BITMAP_CACHE.popitem(last=False)
        total -= old.nbytes


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

    def save_semantic_mask(self, image_stem: str, class_id: int, bitmap) -> str:
        """
        Save a SEMANTIC layer bitmap under a fresh revision name.
        Returns relative path: "masks/<stem>_sem<class_id>_<rev>.png".
        """
        import numpy as np
        from PIL import Image

        fname = f"{image_stem}_sem{class_id}_{uuid.uuid4().hex[:12]}.png"
        arr = np.asarray(bitmap, dtype=np.uint8)
        path = self._masks_dir / fname
        Image.fromarray(arr, mode="L").save(path)
        cached = arr.copy()
        cached.setflags(write=False)
        _cache_put(str(path), cached)
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

    def load_mask_cached(self, mask_png_path: str):
        """
        Like load_mask(), but served from a process-wide LRU cache.
        The returned array is READ-ONLY — copy it before modifying.
        """
        path = self._project_path / mask_png_path
        key = str(path)
        arr = _BITMAP_CACHE.get(key)
        if arr is not None:
            _BITMAP_CACHE.move_to_end(key)
            return arr
        arr = self.load_mask(mask_png_path)
        if arr is None:
            return None
        arr.setflags(write=False)
        _cache_put(key, arr)
        return arr

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

    @staticmethod
    def mask_to_polygons(bitmap, image_w: int,
                         image_h: int) -> list[list[list[float]]]:
        """
        Outer contour of EVERY connected region (largest first), normalized.
        Regions under _MIN_REGION_PX are dropped. Holes are not represented.
        Pass image_w = image_h = 1 to get pixel coordinates.
        """
        import cv2
        import numpy as np

        arr = np.asarray(bitmap, dtype=np.uint8)
        contours, _ = cv2.findContours(
            arr, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        polys: list[tuple[float, list[list[float]]]] = []
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < _MIN_REGION_PX:
                continue
            eps = max(1.0, 0.001 * cv2.arcLength(cnt, True))
            approx = cv2.approxPolyDP(cnt, eps, True)
            if len(approx) < 3:
                continue
            polys.append((area, [[float(pt[0][0]) / image_w,
                                  float(pt[0][1]) / image_h] for pt in approx]))
        polys.sort(key=lambda t: t[0], reverse=True)
        return [p for _, p in polys]

    def semantic_data(self, image_stem: str, class_id: int, bitmap,
                      image_w: int, image_h: int) -> dict:
        """Save a SEMANTIC layer and return its geometry fields for ann.data."""
        import numpy as np

        arr = np.asarray(bitmap, dtype=np.uint8)
        return {
            "mask_png_path": self.save_semantic_mask(image_stem, class_id, arr),
            "polygons": self.mask_to_polygons(arr, image_w, image_h),
            "bbox": self.mask_to_bbox(arr, image_w, image_h),
            "area": float(np.count_nonzero(arr)) / float(max(1, arr.size)),
        }

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
