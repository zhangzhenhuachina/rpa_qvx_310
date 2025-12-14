import os
from typing import Optional

from src.core.types import BBox


class OpenCVTemplateMatcher:
    """使用 OpenCV 进行以图搜图。"""

    def __init__(self, threshold: float = 0.8) -> None:
        self.threshold = threshold
        self._cv2 = self._load_cv2()

    def _load_cv2(self):
        try:
            import cv2  # type: ignore

            return cv2
        except Exception as exc:
            raise RuntimeError("未找到opencv-python，请安装后再使用定位功能") from exc

    def match(self, screenshot_path: str, template_path: str) -> Optional[BBox]:
        if not os.path.exists(screenshot_path):
            return None
        if not os.path.exists(template_path):
            return None

        cv2 = self._cv2
        screenshot = cv2.imread(screenshot_path)
        template = cv2.imread(template_path)

        if screenshot is None or template is None:
            return None

        result = cv2.matchTemplate(screenshot, template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)

        if max_val < self.threshold:
            return None

        height, width = template.shape[:2]
        return BBox(
            x=int(max_loc[0]),
            y=int(max_loc[1]),
            width=int(width),
            height=int(height),
        )
