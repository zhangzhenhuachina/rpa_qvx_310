from __future__ import annotations

from typing import Optional, Tuple


Point = Tuple[int, int]


def draw_rect(
    image_path: str,
    *,
    top_left: Point,
    width: int,
    height: int,
    color: str = "red",
    line_width: int = 4,
) -> Optional[str]:
    try:
        from PIL import Image, ImageDraw  # type: ignore
    except Exception:
        return None

    try:
        image = Image.open(image_path)
        draw = ImageDraw.Draw(image)
        x1, y1 = int(top_left[0]), int(top_left[1])
        x2 = x1 + int(width)
        y2 = y1 + int(height)
        draw.rectangle([x1, y1, x2, y2], outline=color, width=int(line_width))
        image.save(image_path)
        return image_path
    except Exception:
        return None


def draw_center_box(image_path: str, center: Point, *, box_size: Tuple[int, int] = (120, 60)) -> Optional[str]:
    """
    在图片上以 center 为中心画一个红框（用于“推算坐标”的可视化）。
    会原地覆盖保存 image_path；失败返回 None。
    """
    try:
        from PIL import Image, ImageDraw  # type: ignore
    except Exception:
        return None

    try:
        image = Image.open(image_path)
        draw = ImageDraw.Draw(image)
        cx, cy = int(center[0]), int(center[1])
        w, h = int(box_size[0]), int(box_size[1])
        x1 = cx - w // 2
        y1 = cy - h // 2
        x2 = cx + w // 2
        y2 = cy + h // 2
        draw.rectangle([x1, y1, x2, y2], outline="red", width=4)
        image.save(image_path)
        return image_path
    except Exception:
        return None
