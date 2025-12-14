from __future__ import annotations

"""人类化鼠标键盘控制层。
核心思路：
1) 控制层只做“编排”：读取 profile，加载白名单策略，提供工具方法（贝塞尔路径、随机等待、粘贴等）。
2) 具体拟人策略放到策略类中，控制层不写具体行为细节，方便后续扩展。
3) 代码保持简单易读，配合注释，便于维护。
"""

import math
import platform
import random
import time
from typing import List, Tuple

import pyautogui
import pyperclip

from .human_like_profile import ProfileConfig
from .registry import MOUSE_STRATEGIES, TYPING_STRATEGIES


class HumanLikeController:
    """封装鼠标键盘的人类化控制。"""

    def __init__(self, profile: ProfileConfig):
        # 保存 profile，供策略和工具方法读取配置
        self.profile = profile

        # 关闭 pyautogui 全局延迟，保留 FAILSAFE
        pyautogui.PAUSE = 0.0
        pyautogui.MINIMUM_DURATION = 0.0
        pyautogui.MINIMUM_SLEEP = 0.0
        pyautogui.FAILSAFE = True

        # 固定随机种子（如果配置提供），方便复现
        if profile.random_seed is not None:
            random.seed(profile.random_seed)

        # 根据策略名称从白名单映射中取出对应类并实例化
        MouseCls = MOUSE_STRATEGIES[profile.strategies.mouse]
        TypingCls = TYPING_STRATEGIES[profile.strategies.typing]
        self.mouse_strategy = MouseCls()
        self.typing_strategy = TypingCls()

    # -------------------- 对外方法：调用策略与常用操作 --------------------

    def move_and_click(self, x: int, y: int, button: str = "left", clicks: int = 1) -> None:
        """移动到目标位置并点击。"""
        self.mouse_strategy.move(self, x, y)
        self.wait_short()
        self.click(x, y, button=button, clicks=clicks)

    def click_and_type(self, x: int, y: int, text: str, button: str = "left") -> None:
        """移动到输入框点击后，输入文本。"""
        self.move_and_click(x, y, button=button, clicks=1)
        self.type_text(text)

    def type_text(self, text: str) -> None:
        """将文本交给键盘策略处理。"""
        self.typing_strategy.type_text(self, text)

    def click(self, x: int, y: int, button: str = "left", clicks: int = 1) -> None:
        """简单封装 pyautogui.click，保持接口对齐。"""
        pyautogui.click(x=x, y=y, button=button, clicks=clicks, interval=0.0)

    def press_hotkey(self, *keys: str) -> None:
        """按顺序按下组合键，再逆序抬起，模拟人类操作。"""
        if not keys:
            return
        for key in keys:
            pyautogui.keyDown(key)
        for key in reversed(keys):
            pyautogui.keyUp(key)

    def wait_short(self) -> None:
        """短暂停等，使用 profile.wait.short_range。"""
        cfg = self.profile.wait
        self._sleep_random(cfg.short_range[0], cfg.short_range[1])

    def wait_read(self) -> None:
        """阅读型等待，使用 profile.wait.read_range。"""
        cfg = self.profile.wait
        self._sleep_random(cfg.read_range[0], cfg.read_range[1])

    def maybe_long_pause(self) -> None:
        """按概率插入一次长暂停，模拟走神或思考。"""
        cfg = self.profile.wait
        if random.random() <= cfg.long_pause_chance:
            self._sleep_random(cfg.long_pause_range[0], cfg.long_pause_range[1])

    def scroll_smooth(self, total_clicks: int) -> None:
        """平滑滚动：将总滚动量拆分为小步，逐步滚动并随机停顿。"""
        if total_clicks == 0:
            return
        cfg = self.profile.mouse
        step = int(getattr(cfg, "scroll_step", 1))
        pause_range = getattr(cfg, "scroll_pause_range", (0.02, 0.08))
        step = step if step > 0 else 1

        remaining = total_clicks
        direction = 1 if total_clicks > 0 else -1
        while remaining != 0:
            current_step = min(step, abs(remaining)) * direction
            pyautogui.scroll(current_step)
            remaining -= current_step
            self._sleep_random(pause_range[0], pause_range[1])

    # -------------------- 工具方法：供策略内部调用 --------------------

    @staticmethod
    def is_ascii_char(ch: str) -> bool:
        """判断字符是否 ASCII。"""
        return ord(ch) < 128

    def contains_non_ascii(self, text: str) -> bool:
        """检查文本中是否包含非 ASCII 字符。"""
        return any(not self.is_ascii_char(ch) for ch in text)

    @staticmethod
    def _sleep_random(min_s: float, max_s: float) -> None:
        """在指定区间内随机 sleep，保持简单防止 0 或负值。"""
        if max_s < min_s:
            min_s, max_s = max_s, min_s
        delay = random.uniform(min_s, max_s) if max_s > 0 else 0
        if delay > 0:
            time.sleep(delay)

    def _bezier_path(self, start: Tuple[float, float], end: Tuple[float, float], duration: float) -> List[Tuple[float, float]]:
        """生成贝塞尔平滑轨迹点列表。"""
        cfg = self.profile.mouse
        control_points = max(1, int(cfg.control_points))
        jitter_radius = float(getattr(cfg, "jitter_radius", 0.0))

        p0 = start
        p3 = end

        dx = p3[0] - p0[0]
        dy = p3[1] - p0[1]
        distance = math.hypot(dx, dy)
        if distance == 0:
            return []

        def random_control_point(t_ratio: float) -> Tuple[float, float]:
            base_x = p0[0] + dx * t_ratio
            base_y = p0[1] + dy * t_ratio
            if distance == 0:
                normal_x, normal_y = 0.0, 0.0
            else:
                normal_x, normal_y = -dy / distance, dx / distance
            offset = random.uniform(-jitter_radius, jitter_radius)
            return base_x + normal_x * offset, base_y + normal_y * offset

        p1 = random_control_point(0.33)
        p2 = random_control_point(0.66)
        if control_points == 1:
            p2 = p1

        steps_by_time = max(int(duration / 0.006), 3) if duration > 0 else 6
        steps_by_dist = max(int(distance / 8), 4)
        steps = max(steps_by_time, min(steps_by_dist, steps_by_time * 3))

        path: List[Tuple[float, float]] = []
        for i in range(steps):
            t = i / float(steps - 1) if steps > 1 else 1.0
            x = (
                (1 - t) ** 3 * p0[0]
                + 3 * (1 - t) ** 2 * t * p1[0]
                + 3 * (1 - t) * t ** 2 * p2[0]
                + t ** 3 * p3[0]
            )
            y = (
                (1 - t) ** 3 * p0[1]
                + 3 * (1 - t) ** 2 * t * p1[1]
                + 3 * (1 - t) * t ** 2 * p2[1]
                + t ** 3 * p3[1]
            )
            path.append((x, y))
        return path

    def _paste_text(self, text: str) -> None:
        """通过剪贴板粘贴文本，必要时恢复原剪贴板内容。"""
        cfg = self.profile.clipboard

        original_content = None
        restore = bool(getattr(cfg, "restore_original", True))
        if restore:
            try:
                original_content = pyperclip.paste()
            except Exception:
                original_content = None

        pyperclip.copy(text)

        system_name = platform.system().lower()
        paste_keys = ["ctrl", "v"]
        if "darwin" in system_name or "mac" in system_name:
            paste_keys = ["command", "v"]

        min_delay = float(getattr(cfg, "min_copy_delay", 0.05))
        max_delay = float(getattr(cfg, "max_copy_delay", 0.1))
        self._sleep_random(min_delay, max_delay)
        pyautogui.hotkey(*paste_keys)
        self._sleep_random(min_delay, max_delay)

        if restore and original_content is not None:
            try:
                pyperclip.copy(original_content)
            except Exception:
                pass
