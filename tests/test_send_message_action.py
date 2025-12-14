import os
import unittest
from unittest.mock import patch
import time

from src.actions.send_message_action import SendMessageAction
from src.core.runtime_context import RuntimeContext
from src.core.types import BBox
from src.qvx_position.locator import LocateResult


class FakeLocator:
    def __init__(self, input_bbox: BBox, send_bbox: BBox = None) -> None:
        self.input_bbox = input_bbox
        self.send_bbox = send_bbox
        self.calls = []

    def find_bbox(self, target: str):
        self.calls.append(target)
        if target == "消息输入框":
            return self.input_bbox
        if target == "消息发送按钮":
            return self.send_bbox
        return None

    def locate(self, target: str) -> LocateResult:
        bbox = self.find_bbox(target)
        return LocateResult(
            target=target,
            resolution=(1920, 1080),
            template_path="templates/dummy.png",
            screenshot_path="artifacts/screenshots/dummy.png",
            annotated_screenshot_path=None,
            score=0.99 if bbox else 0.1,
            bbox=bbox,
            reason=None if bbox else "no_match",
        )

    def locate_many(self, targets, *, screenshot_path=None, annotated_path=None):
        return {t: self.locate(t) for t in targets}


class FakeSimulator:
    def __init__(self) -> None:
        self.pressed = False
        self.clicked = False
        self.click_points = []

    def press_alt_s(self) -> None:
        self.pressed = True

    def move_and_click(self, x: int, y: int) -> None:
        self.clicked = True
        self.click_point = (x, y)
        self.click_points.append((x, y))


class SendMessageActionTest(unittest.TestCase):
    # 正向：找到发送按钮，使用点击完成发送
    @patch("src.actions.send_message_action.capture_desktop", return_value="after.png")
    def test_click_send_button(self, _mock_capture):
        locator = FakeLocator(
            input_bbox=BBox(0, 0, 10, 10),
            send_bbox=BBox(10, 10, 20, 20),
        )
        simulator = FakeSimulator()
        action = SendMessageAction(
            locator=locator,
            simulator=simulator,
            after_shot_dir="artifacts",
            context=RuntimeContext(),
        )

        success, shot, error = action.execute()

        self.assertTrue(success)
        self.assertTrue(simulator.clicked)
        self.assertEqual(shot, "after.png")
        self.assertIsNone(error)

    # 负向：找不到发送按钮，直接失败
    @patch("src.actions.send_message_action.capture_desktop", return_value=None)
    def test_fail_when_send_missing(self, _mock_capture):
        locator = FakeLocator(input_bbox=None, send_bbox=None)
        simulator = FakeSimulator()
        action = SendMessageAction(
            locator=locator,
            simulator=simulator,
            after_shot_dir="artifacts",
            context=RuntimeContext(),
        )

        success, shot, error = action.execute()

        self.assertFalse(success)
        self.assertIsNone(shot)
        self.assertIsNotNone(error)

    @patch("src.actions.send_message_action.capture_desktop", return_value="after.png")
    def test_use_cached_positions(self, _mock_capture):
        locator = FakeLocator(
            input_bbox=BBox(0, 0, 10, 10),
            send_bbox=BBox(10, 10, 20, 20),
        )
        simulator = FakeSimulator()
        context = RuntimeContext()
        context.update_positions(
            input_center_position=(5, 5),
            send_button_position=(20, 20),
            located_at=time.time(),
        )
        action = SendMessageAction(locator=locator, simulator=simulator, after_shot_dir="artifacts", context=context)

        success, shot, error = action.execute()

        self.assertTrue(success)
        self.assertTrue(simulator.clicked)
        self.assertEqual(locator.calls, [])
        self.assertEqual(shot, "after.png")
        self.assertIsNone(error)

    @patch("src.actions.send_message_action.capture_desktop", return_value="after.png")
    def test_input_from_send_button_offset(self, _mock_capture):
        locator = FakeLocator(
            input_bbox=None,
            send_bbox=BBox(1000, 900, 100, 40),
        )
        simulator = FakeSimulator()
        context = RuntimeContext()
        action = SendMessageAction(locator=locator, simulator=simulator, after_shot_dir="artifacts", context=context)

        success, shot, error = action.execute()

        self.assertTrue(success)
        self.assertEqual(shot, "after.png")
        self.assertIsNone(error)
        # 至少会点击一次（聚焦输入框），且坐标应来自“发送按钮中心点 + 偏移”
        self.assertTrue(simulator.clicked)
        # 第一次点击应是聚焦输入框（蓝框中心点）
        self.assertGreaterEqual(len(simulator.click_points), 1)
        # send_bbox 左上角(1000,900) 宽=100 高=40 => 蓝框宽=200，高=40，左上=(800,900) => center=(900,920)
        self.assertEqual(simulator.click_points[0], (900, 920))


if __name__ == "__main__":
    # 避免 CI 误执行，留空
    pass
