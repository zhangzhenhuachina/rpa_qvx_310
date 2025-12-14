# -*- coding: utf-8 -*-
"""Profile 配置定义与校验。

设计要点：
1) 所有配置使用 dataclass，字段清晰，易扩展。
2) from_dict 做基础校验：类型、正数、区间顺序、概率取值等。
3) from_json_file 只负责读取文件，校验复用 from_dict。
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Tuple


# ------------- Helper validation utilities -------------
# 这些小函数让 from_dict 保持简洁，同时报错信息指向具体字段。

def _expect_type(value: Any, expected_type: type, name: str) -> Any:
    """确保值是指定类型，否则抛出带字段名的错误。"""
    if not isinstance(value, expected_type):
        raise ValueError(f"{name} must be of type {expected_type.__name__}")
    return value


def _expect_positive(number: float, name: str) -> float:
    """确保数值大于 0。"""
    if number <= 0:
        raise ValueError(f"{name} must be greater than 0")
    return number


def _expect_range(number: float, min_value: float, max_value: float, name: str) -> float:
    """确保数值落在 [min_value, max_value] 闭区间内。"""
    if not (min_value <= number <= max_value):
        raise ValueError(f"{name} must be between {min_value} and {max_value}")
    return number


def _expect_ordered_range(min_value: float, max_value: float, name: str) -> Tuple[float, float]:
    """确保区间上界不小于下界。"""
    if max_value < min_value:
        raise ValueError(f"{name}: max value must be >= min value")
    return min_value, max_value


# ------------- 数据类定义 -------------
# 字段命名遵循 profile 描述，便于策略直接读取。


@dataclass
class MouseConfig:
    # 鼠标移动：时长、抖动、控制点、过冲概率与幅度。
    min_duration: float
    max_duration: float
    jitter_radius: float
    jitter_chance: float  # 每一步应用抖动的概率（0-1），降低抖动频率
    control_points: int
    overshoot_chance: float
    overshoot_radius: float
    speed_curve: str  # 速度曲线：linear / ease_in / ease_out / ease_in_out

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MouseConfig":
        min_duration = _expect_positive(float(data["min_duration"]), "mouse.min_duration")
        max_duration = _expect_positive(float(data["max_duration"]), "mouse.max_duration")
        _expect_ordered_range(min_duration, max_duration, "mouse.duration range")

        jitter_radius = _expect_positive(float(data["jitter_radius"]), "mouse.jitter_radius")
        jitter_chance = _expect_range(float(data.get("jitter_chance", 0.4)), 0.0, 1.0, "mouse.jitter_chance")
        control_points = int(_expect_positive(int(data["control_points"]), "mouse.control_points"))
        overshoot_chance = _expect_range(float(data["overshoot_chance"]), 0.0, 1.0, "mouse.overshoot_chance")
        overshoot_radius = _expect_positive(float(data["overshoot_radius"]), "mouse.overshoot_radius")
        speed_curve = str(data.get("speed_curve", "ease_in_out")).strip().lower()
        if speed_curve not in {"linear", "ease_in", "ease_out", "ease_in_out"}:
            raise ValueError("mouse.speed_curve must be one of: linear, ease_in, ease_out, ease_in_out")

        return cls(
            min_duration=min_duration,
            max_duration=max_duration,
            jitter_radius=jitter_radius,
            jitter_chance=jitter_chance,
            control_points=control_points,
            overshoot_chance=overshoot_chance,
            overshoot_radius=overshoot_radius,
            speed_curve=speed_curve,
        )


@dataclass
class KeyboardConfig:
    # 打字：速度范围、打错概率、纠错延迟、标点停顿。
    min_cps: float  # 每秒最少字符数
    max_cps: float  # 每秒最多字符数
    typo_probability: float  # 故意打错的概率
    correction_delay_range: Tuple[float, float]  # 纠错前的延迟区间
    punctuation_pause: float  # 遇到标点时的额外停顿
    punctuation_pause_chance: float  # 触发标点停顿的概率

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "KeyboardConfig":
        min_cps = _expect_positive(float(data["min_cps"]), "keyboard.min_cps")
        max_cps = _expect_positive(float(data["max_cps"]), "keyboard.max_cps")
        _expect_ordered_range(min_cps, max_cps, "keyboard.cps range")

        typo_probability = _expect_range(float(data["typo_probability"]), 0.0, 1.0, "keyboard.typo_probability")

        corr_range_raw = data["correction_delay_range"]
        if not (isinstance(corr_range_raw, (list, tuple)) and len(corr_range_raw) == 2):
            raise ValueError("keyboard.correction_delay_range must be a 2-element list/tuple")
        corr_min = _expect_positive(float(corr_range_raw[0]), "keyboard.correction_delay_range[0]")
        corr_max = _expect_positive(float(corr_range_raw[1]), "keyboard.correction_delay_range[1]")
        correction_delay_range = _expect_ordered_range(corr_min, corr_max, "keyboard.correction_delay_range")

        punctuation_pause = _expect_positive(float(data["punctuation_pause"]), "keyboard.punctuation_pause")
        punctuation_pause_chance = _expect_range(
            float(data["punctuation_pause_chance"]), 0.0, 1.0, "keyboard.punctuation_pause_chance"
        )

        return cls(
            min_cps=min_cps,
            max_cps=max_cps,
            typo_probability=typo_probability,
            correction_delay_range=correction_delay_range,
            punctuation_pause=punctuation_pause,
            punctuation_pause_chance=punctuation_pause_chance,
        )


@dataclass
class WaitConfig:
    # 等待：短等待、阅读等待、长暂停。
    short_range: Tuple[float, float]
    read_range: Tuple[float, float]
    long_pause_chance: float
    long_pause_range: Tuple[float, float]

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WaitConfig":
        short_raw = data["short_range"]
        read_raw = data["read_range"]
        long_raw = data["long_pause_range"]

        if not (isinstance(short_raw, (list, tuple)) and len(short_raw) == 2):
            raise ValueError("wait.short_range must be a 2-element list/tuple")
        if not (isinstance(read_raw, (list, tuple)) and len(read_raw) == 2):
            raise ValueError("wait.read_range must be a 2-element list/tuple")
        if not (isinstance(long_raw, (list, tuple)) and len(long_raw) == 2):
            raise ValueError("wait.long_pause_range must be a 2-element list/tuple")

        short_min = _expect_positive(float(short_raw[0]), "wait.short_range[0]")
        short_max = _expect_positive(float(short_raw[1]), "wait.short_range[1]")
        short_range = _expect_ordered_range(short_min, short_max, "wait.short_range")

        read_min = _expect_positive(float(read_raw[0]), "wait.read_range[0]")
        read_max = _expect_positive(float(read_raw[1]), "wait.read_range[1]")
        read_range = _expect_ordered_range(read_min, read_max, "wait.read_range")

        long_min = _expect_positive(float(long_raw[0]), "wait.long_pause_range[0]")
        long_max = _expect_positive(float(long_raw[1]), "wait.long_pause_range[1]")
        long_pause_range = _expect_ordered_range(long_min, long_max, "wait.long_pause_range")

        long_pause_chance = _expect_range(float(data["long_pause_chance"]), 0.0, 1.0, "wait.long_pause_chance")

        return cls(
            short_range=short_range,
            read_range=read_range,
            long_pause_chance=long_pause_chance,
            long_pause_range=long_pause_range,
        )


@dataclass
class ClipboardConfig:
    # 剪贴板：是否恢复原内容、粘贴前后延迟。
    restore_original: bool
    min_copy_delay: float
    max_copy_delay: float

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ClipboardConfig":
        restore_original = bool(_expect_type(data["restore_original"], bool, "clipboard.restore_original"))
        min_copy_delay = _expect_positive(float(data["min_copy_delay"]), "clipboard.min_copy_delay")
        max_copy_delay = _expect_positive(float(data["max_copy_delay"]), "clipboard.max_copy_delay")
        _expect_ordered_range(min_copy_delay, max_copy_delay, "clipboard.copy_delay")

        return cls(
            restore_original=restore_original,
            min_copy_delay=min_copy_delay,
            max_copy_delay=max_copy_delay,
        )


@dataclass
class StrategiesConfig:
    # 策略名称（白名单由 registry 控制）。
    mouse: str
    typing: str

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StrategiesConfig":
        mouse = _expect_type(data["mouse"], str, "strategies.mouse")
        typing = _expect_type(data["typing"], str, "strategies.typing")
        return cls(mouse=mouse, typing=typing)


@dataclass
class ProfileConfig:
    # 总配置：聚合所有子配置与元信息。
    profile_name: str
    version: str
    mouse: MouseConfig
    keyboard: KeyboardConfig
    wait: WaitConfig
    clipboard: ClipboardConfig
    strategies: StrategiesConfig
    random_seed: Optional[int] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProfileConfig":
        # 逐字段解析与校验，保证类型与取值正确。
        profile_name = _expect_type(data["profile_name"], str, "profile_name")
        version = _expect_type(data["version"], str, "version")

        mouse_cfg = MouseConfig.from_dict(_expect_type(data["mouse"], dict, "mouse"))
        keyboard_cfg = KeyboardConfig.from_dict(_expect_type(data["keyboard"], dict, "keyboard"))
        wait_cfg = WaitConfig.from_dict(_expect_type(data["wait"], dict, "wait"))
        clipboard_cfg = ClipboardConfig.from_dict(_expect_type(data["clipboard"], dict, "clipboard"))
        strategies_cfg = StrategiesConfig.from_dict(_expect_type(data["strategies"], dict, "strategies"))

        random_seed_raw = data.get("random_seed")
        if random_seed_raw is None:
            random_seed: Optional[int] = None
        else:
            random_seed = _expect_type(random_seed_raw, int, "random_seed")

        return cls(
            profile_name=profile_name,
            version=version,
            mouse=mouse_cfg,
            keyboard=keyboard_cfg,
            wait=wait_cfg,
            clipboard=clipboard_cfg,
            strategies=strategies_cfg,
            random_seed=random_seed,
        )

    @classmethod
    def from_json_file(cls, path: str) -> "ProfileConfig":
        """从 JSON 文件加载配置并进行校验。"""
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("Top-level JSON must be an object")
        return cls.from_dict(data)
