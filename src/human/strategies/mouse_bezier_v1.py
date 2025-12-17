from __future__ import annotations

"""基于贝塞尔曲线的拟人鼠标移动策略。
实现思路（保持简单、可读）：
1) 读取 profile 中的鼠标配置（时长、抖动、控制点、过冲概率与幅度）。
2) 计算总时长后，决定是否执行“过冲”路径：先略过目标点，再回到目标。
3) 每段路径使用 controller._bezier_path 生成平滑轨迹点，再在每个点上添加轻微抖动。
4) 使用 pyautogui.moveTo 逐点移动，并通过 controller._sleep_random 控制步进间隔。
"""

import math
import os
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
    def _speed_factor(t: float, mode: str) -> float:
        """返回速度因子（越大越快）。

        设计目标：
        - ease_in_out: 慢-快-慢（两端慢，中间快）
        - ease_in: 慢-快
        - ease_out: 快-慢
        - linear: 匀速
        """
        t = max(0.0, min(1.0, float(t)))
        min_speed = 0.18  # 防止端点速度过低导致延迟爆炸

        if mode == "ease_in_out":
            # sin(pi*t): 0->1->0，天然符合慢-快-慢节奏
            return min_speed + (1.0 - min_speed) * math.sin(math.pi * t)
        if mode == "ease_in":
            # t^2: 0->1，慢起步逐渐加速
            return min_speed + (1.0 - min_speed) * (t * t)
        if mode == "ease_out":
            # (1-t)^2: 1->0，起步快逐渐减速
            u = 1.0 - t
            return min_speed + (1.0 - min_speed) * (u * u)

        return 1.0

    def _compute_step_delays(self, duration: float, steps: int, curve: str) -> List[float]:
        """根据速度曲线为每个路径点分配延迟，总和约等于 duration。

        使用“速度因子”的倒数来分配 delay：速度越快 -> delay 越小；速度越慢 -> delay 越大。
        """
        if steps <= 0:
            return []
        if duration <= 0:
            return [0.0] * steps

        # 让速度节奏有轻微随机波动（更像人），但保持整体“慢-快-慢”的趋势。
        # 设为 0 可禁用：HUMAN_MOUSE_TEMPO_JITTER=0
        try:
            tempo_jitter = float(os.getenv("HUMAN_MOUSE_TEMPO_JITTER", "0.15"))
        except Exception:
            tempo_jitter = 0.15
        tempo_jitter = max(0.0, min(0.6, tempo_jitter))

        # 用少量锚点插值生成“平滑噪声”，避免每一步都随机导致抖动过强。
        anchors = 5
        noise: List[float] = [0.0] * steps
        if tempo_jitter > 0 and steps >= 3:
            anchor_values = [random.uniform(-tempo_jitter, tempo_jitter) for _ in range(anchors)]
            for i in range(steps):
                u = i / float(max(steps - 1, 1))
                pos = u * (anchors - 1)
                idx = int(math.floor(pos))
                frac = pos - idx
                if idx >= anchors - 1:
                    noise[i] = anchor_values[-1]
                else:
                    noise[i] = anchor_values[idx] * (1.0 - frac) + anchor_values[idx + 1] * frac

        delay_weights: List[float] = []
        for i in range(steps):
            t = i / float(max(steps - 1, 1))
            speed = self._speed_factor(t, curve)
            if tempo_jitter > 0:
                speed *= 1.0 + noise[i]

            delay_weights.append(1.0 / max(speed, 0.0001))

        total = sum(delay_weights)
        if total <= 0:
            return [duration / steps] * steps

        return [(duration * w) / total for w in delay_weights]
