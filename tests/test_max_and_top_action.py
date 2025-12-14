import unittest
from unittest.mock import patch

from src.actions.max_and_top_action import MaxAndTopAction


class FakeController:
    def __init__(
        self,
        handle=1,
        activate_ok=True,
        top_ok=True,
    ) -> None:
        self.handle = handle
        self.activate_ok = activate_ok
        self.top_ok = top_ok
        self.called = []

    def find_window(self):
        self.called.append("find")
        return self.handle

    def activate_and_maximize(self, hwnd: int):
        self.called.append(f"activate:{hwnd}")
        return self.activate_ok

    def set_topmost(self, hwnd: int):
        self.called.append(f"top:{hwnd}")
        return self.top_ok


class MaxAndTopActionTest(unittest.TestCase):
    # 正向：找到窗口并置顶成功，返回截图路径
    @patch("src.actions.max_and_top_action.capture_desktop", return_value="shot.png")
    def test_success_flow(self, _mock_capture):
        controller = FakeController(handle=10, activate_ok=True, top_ok=True)
        action = MaxAndTopAction(controller=controller, shot_dir="artifacts")

        success, shot = action.execute()

        self.assertTrue(success)
        self.assertEqual(shot, "shot.png")
        self.assertIn("find", controller.called[0])

    # 负向：未找到窗口时直接失败
    @patch("src.actions.max_and_top_action.capture_desktop", return_value="shot.png")
    def test_fail_when_no_window(self, _mock_capture):
        controller = FakeController(handle=None)
        action = MaxAndTopAction(controller=controller, shot_dir="artifacts")

        success, shot = action.execute()

        self.assertFalse(success)
        self.assertIsNone(shot)

    # 负向：置顶失败时返回失败
    @patch("src.actions.max_and_top_action.capture_desktop", return_value="shot.png")
    def test_fail_when_topmost_error(self, _mock_capture):
        controller = FakeController(handle=5, activate_ok=True, top_ok=False)
        action = MaxAndTopAction(controller=controller, shot_dir="artifacts")

        success, shot = action.execute()

        self.assertFalse(success)
        self.assertIsNone(shot)


if __name__ == "__main__":
    # 避免 CI 误执行，留空
    pass
