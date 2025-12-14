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


class FakeSimulator:
    def __init__(self) -> None:
        self.pressed = False
        self.clicked = False

    def press_alt_s(self) -> None:
        self.pressed = True

    def move_and_click(self, x: int, y: int) -> None:
        self.clicked = True
        self.click_point = (x, y)


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

    # 正向：未找到发送按钮，回退 ALT+S
    @patch("src.actions.send_message_action.capture_desktop", return_value="after.png")
    def test_fallback_alt_s(self, _mock_capture):
        locator = FakeLocator(input_bbox=BBox(0, 0, 10, 10), send_bbox=None)
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
        self.assertTrue(simulator.pressed)
        self.assertEqual(shot, "after.png")
        self.assertIsNone(error)

    # 负向：找不到输入框，直接失败
    @patch("src.actions.send_message_action.capture_desktop", return_value=None)
    def test_fail_when_input_missing(self, _mock_capture):
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


if __name__ == "__main__":
    # 避免 CI 误执行，留空
    pass
