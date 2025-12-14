from __future__ import annotations

"""策略注册表：维护内置策略的白名单映射。
注意：不提供外部修改接口，保持策略来源可控。
"""

from .strategies.mouse_bezier_v1 import BezierMouseStrategyV1
from .strategies.typing_mix_ascii_clipboard_v1 import MixedAsciiClipboardTypingV1

# 鼠标策略白名单
MOUSE_STRATEGIES = {
    "bezier_v1": BezierMouseStrategyV1,
}

# 键盘策略白名单
TYPING_STRATEGIES = {
    "ascii_clipboard_mix_v1": MixedAsciiClipboardTypingV1,
}
