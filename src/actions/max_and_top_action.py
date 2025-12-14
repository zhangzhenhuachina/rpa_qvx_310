import ctypes
import os
from typing import List, Optional, Tuple

from src.core.screenshot import capture_desktop
from src.settings import SCREEN_MAX_AND_TOP


class WindowController:
    """使用 ctypes 定位并控制企业微信窗口。"""

    def __init__(self, targets: Optional[List[str]] = None) -> None:
        # 默认尝试多种标题，避免不同版本窗口标题差异
        self.targets = targets or ["企业微信", "wecom", "wxwork"]
        self.user32 = ctypes.windll.user32

    def find_window(self) -> Optional[int]:
        """枚举顶层窗口，找到包含目标标题的窗口句柄。"""
        handles: List[int] = []
        target_titles = [t.lower() for t in self.targets]

        @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
        def enum_windows_proc(hwnd, _lparam):
            length = self.user32.GetWindowTextLengthW(hwnd)
            if length == 0:
                return True

            buffer = ctypes.create_unicode_buffer(length + 1)
            self.user32.GetWindowTextW(hwnd, buffer, length + 1)
            title = buffer.value.strip().lower()
            if not title:
                return True

            for target in target_titles:
                if target in title:
                    handles.append(hwnd)
                    return False  # 找到后停止枚举
            return True

        self.user32.EnumWindows(enum_windows_proc, 0)
        return handles[0] if handles else None

    def activate_and_maximize(self, hwnd: int) -> bool:
        """恢复窗口并最大化，然后激活到前台。"""
        try:
            SW_RESTORE = 9
            SW_MAXIMIZE = 3
            self.user32.ShowWindow(hwnd, SW_RESTORE)
            self.user32.ShowWindow(hwnd, SW_MAXIMIZE)
            self.user32.SetForegroundWindow(hwnd)
            return True
        except Exception:
            return False

    def set_topmost(self, hwnd: int) -> bool:
        """设置窗口置顶。"""
        try:
            HWND_TOPMOST = -1
            SWP_NOMOVE = 0x0002
            SWP_NOSIZE = 0x0001
            SWP_SHOWWINDOW = 0x0040
            result = self.user32.SetWindowPos(
                hwnd,
                HWND_TOPMOST,
                0,
                0,
                0,
                0,
                SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW,
            )
            return bool(result)
        except Exception:
            return False


class MaxAndTopAction:
    """企业微信置顶与最大化动作。"""

    def __init__(
        self,
        controller: Optional[WindowController] = None,
        shot_dir: str = SCREEN_MAX_AND_TOP,
    ) -> None:
        self.controller = controller or WindowController()
        self.shot_dir = shot_dir

    def execute(self) -> Tuple[bool, Optional[str]]:
        hwnd = self.controller.find_window()
        if not hwnd:
            return False, None

        activated = self.controller.activate_and_maximize(hwnd)
        if not activated:
            return False, None

        topped = self.controller.set_topmost(hwnd)
        if not topped:
            return False, None

        screenshot_path = self._save_screenshot()
        return True, screenshot_path

    def _save_screenshot(self) -> Optional[str]:
        os.makedirs(self.shot_dir, exist_ok=True)
        file_path = os.path.join(self.shot_dir, "max_and_top.png")
        return capture_desktop(file_path)
