"""策略接口定义：鼠标与键盘的拟人化动作。

仅声明接口，具体实现由各策略模块提供。
"""
from __future__ import annotations

from typing import Protocol


class MouseStrategy(Protocol):
    """鼠标策略接口：定义鼠标移动的统一入口。"""

    def move(self, controller, x: int, y: int) -> None:
        """移动鼠标到目标坐标，控制层会提供 controller 用于访问配置和工具函数。"""
        raise NotImplementedError


class TypingStrategy(Protocol):
    """键盘策略接口：定义文本输入的统一入口。"""

    def type_text(self, controller, text: str) -> None:
        """按策略输入文本，controller 提供必要的配置与辅助方法。"""
        raise NotImplementedError
