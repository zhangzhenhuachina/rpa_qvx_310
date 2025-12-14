import unittest
from unittest.mock import patch

from src.core.types import BBox
from src.qvx_position.locator import PositionLocator


class FakeRepository:
    def __init__(self, template_path: str = "template.png") -> None:
        self.template_path = template_path

    def get_template_path(self, target, resolution):
        return self.template_path


class FakeMatcher:
    def __init__(self, bbox: BBox) -> None:
        self.bbox = bbox
        self.called = False

    def match(self, screenshot_path, template_path):
        self.called = True
        return self.bbox


class PositionLocatorTest(unittest.TestCase):
    # 正向：找到模板和截图，返回期望 bbox
    @patch("src.qvx_position.locator.capture_desktop", return_value="screen.png")
    @patch("src.qvx_position.locator.system_info.get_screen_resolution")
    def test_find_bbox_success(self, mock_resolution, _mock_capture):
        mock_resolution.return_value = (1920, 1080)
        bbox = BBox(10, 20, 30, 40)
        locator = PositionLocator(
            repository=FakeRepository(),
            matcher=FakeMatcher(bbox),
        )

        result = locator.find_bbox("消息输入框")
        self.assertEqual(result, bbox)

    # 负向：截图失败，返回 None
    @patch("src.qvx_position.locator.capture_desktop", return_value=None)
    @patch("src.qvx_position.locator.system_info.get_screen_resolution")
    def test_find_bbox_fail_when_screenshot_missing(self, mock_resolution, _mock_capture):
        mock_resolution.return_value = (1920, 1080)
        locator = PositionLocator(
            repository=FakeRepository(),
            matcher=FakeMatcher(BBox(0, 0, 0, 0)),
        )

        result = locator.find_bbox("消息输入框")
        self.assertIsNone(result)
