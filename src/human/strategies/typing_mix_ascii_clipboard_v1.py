from __future__ import annotations

"""混合 ASCII 打字与剪贴板粘贴的拟人化打字策略。
实现思路（保持简单、可读）：
1) 将输入文本拆成 ASCII 段与非 ASCII 段，分别处理。
2) ASCII 段：逐字符打字，基于 cps 随机延迟；按概率制造一次打错再退格；遇到标点可额外停顿。
3) 非 ASCII 段：直接调用 controller._paste_text，由控制层负责剪贴板粘贴。
"""

import random
import string
from typing import List, Tuple

import pyautogui

from . import TypingStrategy


class MixedAsciiClipboardTypingV1(TypingStrategy):
    """用 ASCII 拟人打字与非 ASCII 剪贴板粘贴组合的策略。"""

    def type_text(self, controller, text: str) -> None:
        """按策略输入文本，支持 ASCII 打字与非 ASCII 粘贴。"""
        if not text:
            return

        chunks = self._split_by_ascii(controller, text)

        for is_ascii, chunk in chunks:
            if not chunk:
                continue
            if is_ascii:
                self._type_ascii_chunk(controller, chunk)
            else:
                controller._paste_text(chunk)

    def _split_by_ascii(self, controller, text: str) -> List[Tuple[bool, str]]:
        """按字符连续性拆分 ASCII 与非 ASCII 段。"""
        result: List[Tuple[bool, str]] = []
        if not text:
            return result

        current_is_ascii = controller.is_ascii_char(text[0])
        buffer: List[str] = [text[0]]

        for ch in text[1:]:
            ch_is_ascii = controller.is_ascii_char(ch)
            if ch_is_ascii == current_is_ascii:
                buffer.append(ch)
            else:
                result.append((current_is_ascii, "".join(buffer)))
                buffer = [ch]
                current_is_ascii = ch_is_ascii

        result.append((current_is_ascii, "".join(buffer)))
        return result

    def _type_ascii_chunk(self, controller, chunk: str) -> None:
        """逐字符打出 ASCII 段，带拟人化随机延迟、可选打错与标点停顿。"""
        cfg = controller.profile.keyboard

        punctuation_chars = getattr(cfg, "punctuation_chars", string.punctuation)
        punctuation_pause_min = float(getattr(cfg, "punctuation_pause_min", getattr(cfg, "punctuation_pause", 0.15)))
        punctuation_pause_max = float(getattr(cfg, "punctuation_pause_max", getattr(cfg, "punctuation_pause", 0.3)))

        typo_probability = float(cfg.typo_probability)
        min_cps = float(cfg.min_cps)
        max_cps = float(cfg.max_cps)

        for ch in chunk:
            cps = random.uniform(min_cps, max_cps) if max_cps >= min_cps else min_cps
            delay = 1.0 / cps if cps > 0 else 0.05

            if random.random() < typo_probability:
                wrong_char = random.choice(string.ascii_lowercase)
                pyautogui.write(wrong_char, interval=0)
                controller._sleep_random(delay * 0.3, delay * 0.7)
                pyautogui.press("backspace")
                controller._sleep_random(delay * 0.3, delay * 0.7)

            pyautogui.write(ch, interval=0)
            controller._sleep_random(delay, delay)

            if ch in punctuation_chars:
                controller._sleep_random(punctuation_pause_min, punctuation_pause_max)
