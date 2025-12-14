import os
from dataclasses import asdict, dataclass
from typing import Dict, Optional, Tuple

from src.core import system_info
from src.core.screenshot import capture_desktop
from src.core.types import BBox
from src.qvx_position.matcher import OpenCVTemplateMatcher
from src.qvx_position.template_repository import TemplateRepository


@dataclass(frozen=True)
class LocateResult:
    target: str
    resolution: Optional[Tuple[int, int]]
    template_path: Optional[str]
    screenshot_path: Optional[str]
    annotated_screenshot_path: Optional[str]
    score: Optional[float]
    bbox: Optional[BBox]
    reason: Optional[str]

    def to_dict(self) -> Dict[str, object]:
        data = asdict(self)
        bbox = data.get("bbox")
        if bbox is not None:
            data["bbox"] = {"x": bbox["x"], "y": bbox["y"], "width": bbox["width"], "height": bbox["height"]}
        return data


class PositionLocator:
    """根据屏幕截图和模板，返回元素的 BBox。"""

    def __init__(
        self,
        repository: Optional[TemplateRepository] = None,
        matcher: Optional[OpenCVTemplateMatcher] = None,
    ) -> None:
        self.repository = repository or TemplateRepository()
        self.matcher = matcher or OpenCVTemplateMatcher()

    def find_bbox(self, target: str) -> Optional[BBox]:
        result = self.locate(target)
        return result.bbox

    def _annotate_bbox(self, screenshot_path: str, bbox: BBox) -> Optional[str]:
        try:
            from PIL import Image, ImageDraw  # type: ignore
        except Exception:
            return None

        if not os.path.exists(screenshot_path):
            return None

        base, ext = os.path.splitext(screenshot_path)
        annotated_path = f"{base}_bbox{ext or '.png'}"

        try:
            image = Image.open(screenshot_path)
            draw = ImageDraw.Draw(image)
            x1 = int(bbox.x)
            y1 = int(bbox.y)
            x2 = int(bbox.x + bbox.width)
            y2 = int(bbox.y + bbox.height)
            draw.rectangle([x1, y1, x2, y2], outline="red", width=4)
            image.save(annotated_path)
            return annotated_path
        except Exception:
            return None

    def locate(self, target: str) -> LocateResult:
        resolution = system_info.get_screen_resolution()
        template_path = self.repository.get_template_path(target, resolution)
        if not template_path:
            return LocateResult(
                target=target,
                resolution=resolution,
                template_path=None,
                screenshot_path=None,
                annotated_screenshot_path=None,
                score=None,
                bbox=None,
                reason="template_not_found",
            )

        screenshot_path = capture_desktop()
        if not screenshot_path:
            return LocateResult(
                target=target,
                resolution=resolution,
                template_path=template_path,
                screenshot_path=None,
                annotated_screenshot_path=None,
                score=None,
                bbox=None,
                reason="screenshot_failed",
            )

        match_with_score = getattr(self.matcher, "match_with_score", None)
        if callable(match_with_score):
            bbox, score = match_with_score(screenshot_path, template_path)
        else:
            bbox = self.matcher.match(screenshot_path, template_path)
            score = None
        if not bbox:
            return LocateResult(
                target=target,
                resolution=resolution,
                template_path=template_path,
                screenshot_path=screenshot_path,
                annotated_screenshot_path=None,
                score=score,
                bbox=None,
                reason="no_match",
            )

        annotated = self._annotate_bbox(screenshot_path, bbox)
        return LocateResult(
            target=target,
            resolution=resolution,
            template_path=template_path,
            screenshot_path=screenshot_path,
            annotated_screenshot_path=annotated,
            score=score,
            bbox=bbox,
            reason=None,
        )
