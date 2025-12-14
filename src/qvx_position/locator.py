from typing import Optional

from src.core import system_info
from src.core.screenshot import capture_desktop
from src.core.types import BBox
from src.qvx_position.matcher import OpenCVTemplateMatcher
from src.qvx_position.template_repository import TemplateRepository


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
        resolution = system_info.get_screen_resolution()
        template_path = self.repository.get_template_path(target, resolution)
        if not template_path:
            return None

        screenshot_path = capture_desktop()
        if not screenshot_path:
            return None

        return self.matcher.match(screenshot_path, template_path)
