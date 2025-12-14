import logging
import os
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

from src.core.screenshot import capture_desktop
from src.core.runtime_context import RuntimeContext, runtime_context
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
        context: Optional[RuntimeContext] = None,
    ) -> None:
        self.locator = locator or PositionLocator()
        self.simulator = simulator or InputSimulator()
        self.after_shot_dir = after_shot_dir
        self.context = context or runtime_context
        self.last_debug: Optional[Dict[str, Any]] = None

    def execute(self) -> Tuple[bool, Optional[str], Optional[str]]:
        logger = logging.getLogger(__name__)
        debug: Dict[str, Any] = {"steps": []}

        snap = self.context.snapshot()
        input_center = snap.input_center_position
        if input_center:
            debug["steps"].append({"focus_input_cached": {"x": input_center[0], "y": input_center[1]}})
        else:
            input_loc = self.locator.locate("消息输入框")
            debug["steps"].append({"locate_input": input_loc.to_dict()})
            if not input_loc.bbox:
                self.last_debug = debug
                logger.error("SendMessageAction failed: input box not found debug=%s", debug)
                return False, None, f"未定位到消息输入框（{input_loc.reason}）"
            input_center = (
                int(input_loc.bbox.x + input_loc.bbox.width // 2),
                int(input_loc.bbox.y + input_loc.bbox.height // 2),
            )
            self.context.update_positions(input_center_position=input_center, located_at=datetime.now().timestamp())

        try:
            # 先点一下输入框，确保焦点在输入区
            self._click_point(input_center[0], input_center[1])
            debug["steps"].append({"focus_input": {"x": input_center[0], "y": input_center[1]}})
        except Exception as exc:
            self.last_debug = debug
            logger.exception("SendMessageAction failed: focus input error=%s debug=%s", exc, debug)
            return False, None, f"点击输入框失败：{type(exc).__name__}: {exc}"

        snap = self.context.snapshot()
        send_center = snap.send_button_position
        send_loc = None
        if not send_center:
            send_loc = self.locator.locate("消息发送按钮")
            debug["steps"].append({"locate_send_button": send_loc.to_dict()})
            if send_loc.bbox:
                send_center = (
                    int(send_loc.bbox.x + send_loc.bbox.width // 2),
                    int(send_loc.bbox.y + send_loc.bbox.height // 2),
                )
                self.context.update_positions(send_button_position=send_center, located_at=datetime.now().timestamp())
        try:
            if send_center:
                self._click_point(send_center[0], send_center[1])
                debug["steps"].append({"click_send_button": True})
            else:
                self.simulator.press_alt_s()
                debug["steps"].append({"fallback_alt_s": True})
        except Exception as exc:
            self.last_debug = debug
            logger.exception("SendMessageAction failed: send action error=%s debug=%s", exc, debug)
            return False, None, f"触发发送失败：{type(exc).__name__}: {exc}"

        screenshot_path = self._save_after_screenshot()
        if not screenshot_path:
            self.last_debug = debug
            logger.error("SendMessageAction failed: screenshot save failed debug=%s", debug)
            return False, None, "截图失败"

        debug["after_screenshot"] = screenshot_path
        self.last_debug = debug
        logger.info("SendMessageAction ok screenshot=%s", screenshot_path)
        return True, screenshot_path, None

    def _click_point(self, x: int, y: int) -> None:
        self.simulator.move_and_click(int(x), int(y))

    def _save_after_screenshot(self) -> Optional[str]:
        os.makedirs(self.after_shot_dir, exist_ok=True)
        file_path = os.path.join(self.after_shot_dir, "send_finish.png")
        return capture_desktop(file_path)
