import os
from typing import Optional, Tuple

from src.core.screenshot import capture_desktop
from src.qvx_position.locator import PositionLocator
from src.settings import SCREEN_SEND_MSG_AFTER


class InputSimulator:
    """键盘鼠标仿真封装，便于后续替换为 profile 版。"""

    def __init__(self) -> None:
        self._impl = self._load_impl()

    def _load_impl(self):
        try:
            import pyautogui  # type: ignore

            pyautogui.FAILSAFE = False
            return pyautogui
        except Exception as exc:
            raise RuntimeError("未找到 pyautogui，无法执行仿真输入") from exc

    def press_alt_s(self) -> None:
        self._impl.hotkey("alt", "s")

    def move_and_click(self, x: int, y: int) -> None:
        self._impl.moveTo(x, y)
        self._impl.click()


class SendMessageAction:
    """发送消息动作：定位输入框并提交。"""

    def __init__(
        self,
        locator: Optional[PositionLocator] = None,
        simulator: Optional[InputSimulator] = None,
        after_shot_dir: str = SCREEN_SEND_MSG_AFTER,
    ) -> None:
        self.locator = locator or PositionLocator()
        self.simulator = simulator or InputSimulator()
        self.after_shot_dir = after_shot_dir

    def execute(self) -> Tuple[bool, Optional[str]]:
        input_bbox = self.locator.find_bbox("消息输入框")
        if not input_bbox:
            return False, None

        send_button_bbox = self.locator.find_bbox("消息发送按钮")
        try:
            if send_button_bbox:
                self._click_center(send_button_bbox)
            else:
                self.simulator.press_alt_s()
        except Exception:
            return False, None

        screenshot_path = self._save_after_screenshot()
        return True, screenshot_path

    def _click_center(self, bbox) -> None:
        center_x = bbox.x + bbox.width // 2
        center_y = bbox.y + bbox.height // 2
        self.simulator.move_and_click(center_x, center_y)

    def _save_after_screenshot(self) -> Optional[str]:
        os.makedirs(self.after_shot_dir, exist_ok=True)
        file_path = os.path.join(self.after_shot_dir, "send_finish.png")
        return capture_desktop(file_path)
