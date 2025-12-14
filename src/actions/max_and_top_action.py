import ctypes
import logging
import os
from ctypes import wintypes
from typing import List, Optional, Tuple

from src.core.screenshot import capture_desktop
from src.settings import SCREEN_MAX_AND_TOP


class WindowController:
    """使用 ctypes 定位并控制企业微信窗口。"""

    def __init__(self, targets: Optional[List[str]] = None) -> None:
        # 默认尝试多种标题，避免不同版本窗口标题差异
        self.targets = targets or ["企业微信", "wecom", "wxwork"]
        self.user32 = ctypes.WinDLL("user32", use_last_error=True)
        self.kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self._last_seen_titles: List[str] = []
        self._configure_winapi()

    def _configure_winapi(self) -> None:
        # 明确声明 argtypes/restype，避免 HWND 在 64 位环境下被截断导致 1400（无效窗口句柄）
        self.user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
        self.user32.GetWindowTextLengthW.restype = ctypes.c_int

        self.user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
        self.user32.GetWindowTextW.restype = ctypes.c_int

        self.user32.EnumWindows.restype = wintypes.BOOL

        self.user32.IsWindow.argtypes = [wintypes.HWND]
        self.user32.IsWindow.restype = wintypes.BOOL

        self.user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
        self.user32.ShowWindow.restype = wintypes.BOOL

        self.user32.SetForegroundWindow.argtypes = [wintypes.HWND]
        self.user32.SetForegroundWindow.restype = wintypes.BOOL

        self.user32.SetWindowPos.argtypes = [
            wintypes.HWND,
            wintypes.HWND,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_uint,
        ]
        self.user32.SetWindowPos.restype = wintypes.BOOL

    def get_last_seen_titles(self) -> List[str]:
        return list(self._last_seen_titles)

    def _last_error_message(self) -> str:
        error_code = ctypes.get_last_error()
        if not error_code:
            return "unknown"

        FORMAT_MESSAGE_FROM_SYSTEM = 0x00001000
        FORMAT_MESSAGE_IGNORE_INSERTS = 0x00000200
        buffer = ctypes.create_unicode_buffer(1024)
        self.kernel32.FormatMessageW(
            FORMAT_MESSAGE_FROM_SYSTEM | FORMAT_MESSAGE_IGNORE_INSERTS,
            None,
            error_code,
            0,
            buffer,
            len(buffer),
            None,
        )
        message = buffer.value.strip() or "unknown"
        return f"{error_code}: {message}"

    def find_window(self) -> Tuple[Optional[int], List[str]]:
        """枚举顶层窗口，找到包含目标标题的窗口句柄。"""
        handles: List[int] = []
        seen_titles: List[str] = []
        target_titles = [t.lower() for t in self.targets]

        EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

        @EnumWindowsProc
        def enum_windows_proc(hwnd, _lparam):
            length = self.user32.GetWindowTextLengthW(hwnd)
            if length == 0:
                return True

            buffer = ctypes.create_unicode_buffer(length + 1)
            self.user32.GetWindowTextW(hwnd, buffer, length + 1)
            title = buffer.value.strip().lower()
            if not title:
                return True

            if len(seen_titles) < 50:
                seen_titles.append(title)

            for target in target_titles:
                if target in title:
                    handles.append(int(hwnd))
                    return False  # 找到后停止枚举
            return True

        self.user32.EnumWindows.argtypes = [EnumWindowsProc, wintypes.LPARAM]
        self.user32.EnumWindows(enum_windows_proc, 0)
        self._last_seen_titles = seen_titles
        return (handles[0] if handles else None), seen_titles

    def activate_and_maximize(self, hwnd: int) -> Tuple[bool, Optional[str]]:
        """恢复窗口并最大化，然后激活到前台。"""
        if not bool(self.user32.IsWindow(wintypes.HWND(hwnd))):
            return False, "IsWindow=false (1400: 无效的窗口句柄)"

        try:
            SW_RESTORE = 9
            SW_MAXIMIZE = 3
            h = wintypes.HWND(hwnd)
            self.user32.ShowWindow(h, SW_RESTORE)
            self.user32.ShowWindow(h, SW_MAXIMIZE)
            if not self.user32.SetForegroundWindow(h):
                return False, f"SetForegroundWindow failed ({self._last_error_message()})"
            return True, None
        except Exception as exc:
            return False, f"{type(exc).__name__}: {exc}"

    def set_topmost(self, hwnd: int) -> Tuple[bool, Optional[str]]:
        """设置窗口置顶。"""
        if not bool(self.user32.IsWindow(wintypes.HWND(hwnd))):
            return False, "IsWindow=false (1400: 无效的窗口句柄)"

        try:
            HWND_TOPMOST = wintypes.HWND(-1)
            SWP_NOMOVE = 0x0002
            SWP_NOSIZE = 0x0001
            SWP_SHOWWINDOW = 0x0040
            result = self.user32.SetWindowPos(
                wintypes.HWND(hwnd),
                HWND_TOPMOST,
                0,
                0,
                0,
                0,
                SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW,
            )
            if not bool(result):
                return False, f"SetWindowPos failed ({self._last_error_message()})"
            return True, None
        except Exception as exc:
            return False, f"{type(exc).__name__}: {exc}"


class MaxAndTopAction:
    """企业微信置顶与最大化动作。"""

    def __init__(
        self,
        controller: Optional[WindowController] = None,
        shot_dir: str = SCREEN_MAX_AND_TOP,
    ) -> None:
        self.controller = controller or WindowController()
        self.shot_dir = shot_dir

    def execute(self) -> Tuple[bool, Optional[str], Optional[str]]:
        logger = logging.getLogger(__name__)

        hwnd, seen_titles = self.controller.find_window()
        if not hwnd:
            sample_titles = ", ".join(seen_titles[:5]) if seen_titles else "none"
            targets = getattr(self.controller, "targets", None)
            reason = (
                "未找到企业微信窗口（可能已启动但窗口未显示/标题不匹配）。"
                f" targets={targets} sample_titles=[{sample_titles}]"
            )
            logger.error(reason)
            return False, None, reason

        # 句柄可能在极短时间内失效（例如窗口在切换/重建），遇到 1400 时重找一次
        activated, activate_error = self.controller.activate_and_maximize(hwnd)
        if not activated:
            if "1400" in (activate_error or ""):
                logger.warning("activate failed with 1400, retry find_window once hwnd=%s", hwnd)
                hwnd2, _ = self.controller.find_window()
                if hwnd2:
                    hwnd = hwnd2
                    activated, activate_error = self.controller.activate_and_maximize(hwnd)
                    if activated:
                        activate_error = None
            reason = f"激活/最大化失败 hwnd={hwnd} error={activate_error or 'unknown'}"
            logger.error(reason)
            return False, None, reason

        topped, top_error = self.controller.set_topmost(hwnd)
        if not topped:
            if "1400" in (top_error or ""):
                logger.warning("topmost failed with 1400, retry find_window once hwnd=%s", hwnd)
                hwnd2, _ = self.controller.find_window()
                if hwnd2:
                    hwnd = hwnd2
                    topped, top_error = self.controller.set_topmost(hwnd)
                    if topped:
                        top_error = None
            reason = f"置顶失败 hwnd={hwnd} error={top_error or 'unknown'}"
            logger.error(reason)
            return False, None, reason

        screenshot_path = self._save_screenshot()
        if not screenshot_path:
            reason = "截图失败（capture_desktop 返回 None）"
            logger.error(reason)
            return False, None, reason

        logger.info("MaxAndTopAction ok hwnd=%s screenshot=%s", hwnd, screenshot_path)
        return True, screenshot_path, None

    def _save_screenshot(self) -> Optional[str]:
        os.makedirs(self.shot_dir, exist_ok=True)
        file_path = os.path.join(self.shot_dir, "max_and_top.png")
        return capture_desktop(file_path)
