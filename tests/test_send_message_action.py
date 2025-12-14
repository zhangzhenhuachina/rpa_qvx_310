import os
import unittest
from unittest.mock import patch

from src.actions.send_message_action import SendMessageAction
from src.core.types import BBox


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
        action = SendMessageAction(locator=locator, simulator=simulator, after_shot_dir="artifacts")

        success, shot = action.execute()

        self.assertTrue(success)
        self.assertTrue(simulator.clicked)
        self.assertEqual(shot, "after.png")

    # 正向：未找到发送按钮，回退 ALT+S
    @patch("src.actions.send_message_action.capture_desktop", return_value="after.png")
    def test_fallback_alt_s(self, _mock_capture):
        locator = FakeLocator(input_bbox=BBox(0, 0, 10, 10), send_bbox=None)
        simulator = FakeSimulator()
        action = SendMessageAction(locator=locator, simulator=simulator, after_shot_dir="artifacts")

        success, shot = action.execute()

        self.assertTrue(success)
        self.assertTrue(simulator.pressed)
        self.assertEqual(shot, "after.png")

    # 负向：找不到输入框，直接失败
    @patch("src.actions.send_message_action.capture_desktop", return_value=None)
    def test_fail_when_input_missing(self, _mock_capture):
        locator = FakeLocator(input_bbox=None, send_bbox=None)
        simulator = FakeSimulator()
        action = SendMessageAction(locator=locator, simulator=simulator, after_shot_dir="artifacts")

        success, shot = action.execute()

        self.assertFalse(success)
        self.assertIsNone(shot)


if __name__ == "__main__":
    # 避免 CI 误执行，留空
    pass
