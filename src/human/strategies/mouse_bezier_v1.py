from __future__ import annotations

"""基于贝塞尔曲线的拟人鼠标移动策略。
实现思路（保持简单、可读）：
1) 读取 profile 中的鼠标配置（时长、抖动、控制点、过冲概率与幅度）。
2) 计算总时长后，决定是否执行“过冲”路径：先略过目标点，再回到目标。
3) 每段路径使用 controller._bezier_path 生成平滑轨迹点，再在每个点上添加轻微抖动。
4) 使用 pyautogui.moveTo 逐点移动，并通过 controller._sleep_random 控制步进间隔。
"""

import math
import random
import time
from typing import List, Tuple

import pyautogui

from . import MouseStrategy


class BezierMouseStrategyV1(MouseStrategy):
    """通过贝塞尔曲线和平滑分段实现拟人化鼠标移动。"""

    def move(self, controller, x: int, y: int) -> None:
        """移动鼠标到 (x, y)，可能带有轻微抖动与过冲效果。"""
        cfg = controller.profile.mouse

        start_x, start_y = pyautogui.position()
        target: Tuple[float, float] = (float(x), float(y))
        start: Tuple[float, float] = (float(start_x), float(start_y))

        total_duration = random.uniform(cfg.min_duration, cfg.max_duration)

        def jitter(px: float, py: float) -> Tuple[float, float]:
            if cfg.jitter_radius <= 0:
                return px, py
            if random.random() > cfg.jitter_chance:
                return px, py
            angle = random.uniform(0.0, 2.0 * math.pi)
            radius = random.uniform(0.0, cfg.jitter_radius * 0.6)
            return px + math.cos(angle) * radius, py + math.sin(angle) * radius

        segments: List[Tuple[Tuple[float, float], Tuple[float, float], float]] = []
        use_overshoot = random.random() < cfg.overshoot_chance
        if use_overshoot:
            angle = random.uniform(0.0, 2.0 * math.pi)
            radius = random.uniform(0.1 * cfg.overshoot_radius, cfg.overshoot_radius)
            overshoot_point = (
                target[0] + math.cos(angle) * radius,
                target[1] + math.sin(angle) * radius,
            )
            first_duration = max(total_duration * 0.7, cfg.min_duration * 0.3)
            second_duration = max(total_duration * 0.3, cfg.min_duration * 0.2)
            segments.append((start, overshoot_point, first_duration))
            segments.append((overshoot_point, target, second_duration))
        else:
            segments.append((start, target, total_duration))

        for seg_start, seg_end, seg_duration in segments:
            path = controller._bezier_path(seg_start, seg_end, seg_duration)
            if not path:
                pyautogui.moveTo(seg_end[0], seg_end[1])
                continue

            delays = self._compute_step_delays(seg_duration, len(path), cfg.speed_curve)

            for (px, py), delay in zip(path, delays):
                jitter_x, jitter_y = jitter(px, py)
                pyautogui.moveTo(jitter_x, jitter_y)
                if delay > 0:
                    time.sleep(delay)

        pyautogui.moveTo(target[0], target[1])

    @staticmethod
    def _ease(t: float, mode: str) -> float:
        """简单的速度曲线函数。"""
        if mode == "ease_in":
            return t * t
        if mode == "ease_out":
            return 1 - (1 - t) * (1 - t)
        if mode == "ease_in_out":
            return t * t * (3 - 2 * t)
        return t

    def _compute_step_delays(self, duration: float, steps: int, curve: str) -> List[float]:
        """根据速度曲线为每个路径点分配延迟，总和约等于 duration。"""
        if steps <= 0:
            return []
        if duration <= 0:
            return [0.0] * steps

        weights: List[float] = []
        for i in range(steps):
            t = i / float(max(steps - 1, 1))
            weight = self._ease(t, curve)
            weights.append(max(weight, 0.0001))
        total_weight = sum(weights)
        if total_weight <= 0:
            return [duration / steps] * steps

        delays = [(duration * w) / total_weight for w in weights]
        return delays
