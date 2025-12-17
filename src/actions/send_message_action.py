import logging
import os
import math
import random
import time
from typing import Any, Dict, Optional, Tuple

from src.human.controller import HumanLikeController
from src.human.human_like_profile import ProfileConfig
from src.core.annotate import draw_rect
from src.core.screenshot import capture_desktop
from src.core.runtime_context import RuntimeContext, runtime_context
from src.core.screenshot import CAPTURE_LOCK
from src.qvx_position.locator import PositionLocator
from src.settings import SCREEN_SEND_MSG_AFTER


class InputSimulator:
    """键盘鼠标仿真封装，便于后续替换为 profile 版。"""

    def __init__(self) -> None:
        self._impl = self._load_impl()

    def _load_impl(self):
        profile_path = os.getenv("HUMAN_PROFILE_PATH", os.path.join("src", "human", "profiles", "demo_profile.json"))
        speed = float(os.getenv("HUMAN_MOUSE_SPEED", "1.0"))
        if speed <= 0:
            raise ValueError("HUMAN_MOUSE_SPEED must be > 0")

        profile = ProfileConfig.from_json_file(profile_path)
        # speed>1 => move faster => shorter duration; speed<1 => slower => longer duration.
        profile.mouse.min_duration = max(0.001, float(profile.mouse.min_duration) / speed)
        profile.mouse.max_duration = max(profile.mouse.min_duration, float(profile.mouse.max_duration) / speed)
        return HumanLikeController(profile)

    def press_alt_s(self) -> None:
        self._impl.press_hotkey("alt", "s")

    def move_and_click(self, x: int, y: int) -> None:
        self._impl.move_and_click(int(x), int(y))


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
        send_center = snap.send_button_position
        if input_center and send_center:
            debug["steps"].append(
                {
                    "use_cached_positions": {
                        "input": {"x": input_center[0], "y": input_center[1]},
                        "send": {"x": send_center[0], "y": send_center[1]},
                    }
                }
            )
        else:
            locate_screenshot = os.path.join("artifacts", "screenshots", "locate.png")
            locate_annotated = os.path.join("artifacts", "screenshots", "locate_annotated.png")
            with CAPTURE_LOCK:
                results = self.locator.locate_many(
                    ["消息发送按钮"],
                    screenshot_path=locate_screenshot,
                    annotated_path=locate_annotated,
                )
                send_loc = results.get("消息发送按钮")
            if send_loc:
                debug["steps"].append({"locate_send_button": send_loc.to_dict()})

            if send_loc and send_loc.bbox:
                send_center = (
                    int(send_loc.bbox.x + send_loc.bbox.width // 2),
                    int(send_loc.bbox.y + send_loc.bbox.height // 2),
                )

            if not send_center:
                self.last_debug = debug
                logger.error("SendMessageAction failed: send button not found debug=%s", debug)
                return False, None, "未定位到消息发送按钮"

            send_x1 = int(send_loc.bbox.x)
            send_y1 = int(send_loc.bbox.y)
            send_w = int(send_loc.bbox.width)
            send_h = int(send_loc.bbox.height)
            data_w = max(1, send_w * 2)
            data_h = max(1, send_h)
            # 蓝框完全在红框左侧且不重叠，并且两者连着：蓝框右边界=红框左边界
            data_x = int(send_x1 - data_w)
            data_y = int(send_y1)

            try:
                with CAPTURE_LOCK:
                    draw_rect(
                        locate_annotated,
                        top_left=(data_x, data_y),
                        width=data_w,
                        height=data_h,
                        color="blue",
                    )
            except Exception:
                pass

            input_center = (int(data_x + data_w // 2), int(data_y + data_h // 2))

            debug["steps"].append(
                {
                    "input_rect_from_send_button_topleft": {
                        "send_x": send_center[0],
                        "send_y": send_center[1],
                        "send_x1": send_x1,
                        "send_y1": send_y1,
                        "send_w": send_w,
                        "send_h": send_h,
                        "data_top_left": {"x": data_x, "y": data_y},
                        "data_width": data_w,
                        "data_height": data_h,
                        "input_center": {"x": input_center[0], "y": input_center[1]},
                    }
                }
            )

            self.context.update_positions(
                input_center_position=input_center,
                send_button_position=send_center,
                located_at=time.time(),
                locate_screenshot=(send_loc.screenshot_path if send_loc else locate_screenshot),
                locate_annotated_screenshot=(send_loc.annotated_screenshot_path if send_loc else locate_annotated),
            )

        try:
            # 先点一下输入框，确保焦点在输入区
            click_x, click_y = self._click_input_center_with_jitter(input_center[0], input_center[1])
            debug["steps"].append(
                {
                    "focus_input": {
                        "center": {"x": input_center[0], "y": input_center[1]},
                        "click": {"x": click_x, "y": click_y},
                    }
                }
            )
        except Exception as exc:
            self.last_debug = debug
            logger.exception("SendMessageAction failed: focus input error=%s debug=%s", exc, debug)
            return False, None, f"点击输入框失败：{type(exc).__name__}: {exc}"

        if not send_center:
            debug["steps"].append({"send_button_missing": True})
        try:
            if send_center:
                self._click_point(send_center[0], send_center[1])
                debug["steps"].append({"click_send_button": True})
                logger.info("SendMessageAction send_method=click_send_button")
            else:
                self.simulator.press_alt_s()
                debug["steps"].append({"fallback_alt_s": True})
                logger.info("SendMessageAction send_method=alt_s")
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

    def _click_input_center_with_jitter(self, center_x: int, center_y: int) -> Tuple[int, int]:
        radius = int(os.getenv("INPUT_CLICK_RADIUS_PX", "5"))
        if radius <= 0:
            self._click_point(center_x, center_y)
            return int(center_x), int(center_y)

        angle = random.uniform(0.0, 2.0 * math.pi)
        r = radius * math.sqrt(random.uniform(0.0, 1.0))
        x = int(round(center_x + math.cos(angle) * r))
        y = int(round(center_y + math.sin(angle) * r))
        self._click_point(x, y)
        return x, y

    def _save_after_screenshot(self) -> Optional[str]:
        os.makedirs(self.after_shot_dir, exist_ok=True)
        file_path = os.path.join(self.after_shot_dir, "send_finish.png")
        return capture_desktop(file_path)
