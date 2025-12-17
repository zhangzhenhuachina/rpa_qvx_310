import ctypes
import csv
import logging
import os
from ctypes import wintypes
from io import StringIO
from subprocess import run
from time import sleep
from typing import Dict, List, Optional, Set, Tuple

from src.core.screenshot import capture_desktop
from src.settings import SCREEN_MAX_AND_TOP


class WindowController:
    """使用 ctypes 定位并控制企业微信窗口。"""

    def __init__(self, targets: Optional[List[str]] = None) -> None:
        # 默认尝试多种标题，避免不同版本窗口标题差异
        self.targets = targets or ["企业微信", "wecom", "wxwork"]
        self.process_names = ["wxwork.exe", "wecom.exe", "wechatwork.exe"]
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

        self.user32.IsWindowVisible.argtypes = [wintypes.HWND]
        self.user32.IsWindowVisible.restype = wintypes.BOOL

        self.user32.GetWindow.argtypes = [wintypes.HWND, ctypes.c_uint]
        self.user32.GetWindow.restype = wintypes.HWND

        self.user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
        self.user32.GetWindowRect.restype = wintypes.BOOL

        self.user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
        self.user32.ShowWindow.restype = wintypes.BOOL

        self.user32.SetForegroundWindow.argtypes = [wintypes.HWND]
        self.user32.SetForegroundWindow.restype = wintypes.BOOL

        self.user32.BringWindowToTop.argtypes = [wintypes.HWND]
        self.user32.BringWindowToTop.restype = wintypes.BOOL

        self.user32.SetActiveWindow.argtypes = [wintypes.HWND]
        self.user32.SetActiveWindow.restype = wintypes.HWND

        self.user32.GetForegroundWindow.argtypes = []
        self.user32.GetForegroundWindow.restype = wintypes.HWND

        self.user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
        self.user32.GetWindowThreadProcessId.restype = wintypes.DWORD

        self.user32.AttachThreadInput.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.BOOL]
        self.user32.AttachThreadInput.restype = wintypes.BOOL

        self.kernel32.GetCurrentThreadId.argtypes = []
        self.kernel32.GetCurrentThreadId.restype = wintypes.DWORD

        self.user32.IsZoomed.argtypes = [wintypes.HWND]
        self.user32.IsZoomed.restype = wintypes.BOOL

        get_long_ptr = getattr(self.user32, "GetWindowLongPtrW", None)
        if get_long_ptr is not None:
            get_long_ptr.argtypes = [wintypes.HWND, ctypes.c_int]
            get_long_ptr.restype = ctypes.c_longlong
        else:
            self.user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
            self.user32.GetWindowLongW.restype = ctypes.c_long

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

    def _hwnd_to_int(self, hwnd) -> int:
        if hwnd is None:
            return 0
        if isinstance(hwnd, int):
            return hwnd
        if isinstance(hwnd, (bytes, bytearray)):
            return int.from_bytes(bytes(hwnd), "little", signed=False)
        if isinstance(hwnd, ctypes.c_void_p):
            return int(hwnd.value or 0)
        value = getattr(hwnd, "value", None)
        if isinstance(value, int):
            return value
        if isinstance(value, (bytes, bytearray)):
            return int.from_bytes(bytes(value), "little", signed=False)
        return int(value or 0)

    def _get_window_title(self, hwnd: wintypes.HWND) -> str:
        try:
            length = self.user32.GetWindowTextLengthW(hwnd)
            if length <= 0:
                return ""
            buffer = ctypes.create_unicode_buffer(length + 1)
            self.user32.GetWindowTextW(hwnd, buffer, length + 1)
            return buffer.value.strip()
        except Exception:
            return ""

    def _get_window_pid(self, hwnd: wintypes.HWND) -> int:
        pid = wintypes.DWORD(0)
        try:
            self.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        except Exception:
            return 0
        return int(pid.value or 0)

    def _get_candidate_pids(self) -> Set[int]:
        try:
            completed = run(
                ["tasklist", "/fo", "csv", "/nh"],
                capture_output=True,
                text=True,
                check=False,
            )
        except Exception:
            return set()

        output = (completed.stdout or "").strip()
        if not output:
            return set()

        wanted = {n.lower() for n in self.process_names}
        pids: Set[int] = set()
        reader = csv.reader(StringIO(output))
        for row in reader:
            if not row or len(row) < 2:
                continue
            image = (row[0] or "").strip().strip('"').lower()
            if image not in wanted:
                continue
            try:
                pids.add(int(row[1]))
            except Exception:
                continue
        return pids

    def describe_window(self, hwnd_int: int) -> Dict[str, object]:
        hwnd = wintypes.HWND(hwnd_int)
        title = self._get_window_title(hwnd)
        pid = self._get_window_pid(hwnd)
        rect = wintypes.RECT()
        rect_ok = bool(self.user32.GetWindowRect(hwnd, ctypes.byref(rect)))
        fg = self.user32.GetForegroundWindow()
        fg_int = self._hwnd_to_int(fg)
        WS_EX_TOPMOST = 0x00000008
        exstyle = self._get_exstyle(hwnd)
        return {
            "hwnd": hwnd_int,
            "title": title,
            "pid": pid,
            "rect": [rect.left, rect.top, rect.right, rect.bottom] if rect_ok else None,
            "is_zoomed": bool(self.user32.IsZoomed(hwnd)),
            "is_topmost": (exstyle & WS_EX_TOPMOST) != 0,
            "foreground_hwnd": fg_int,
            "is_foreground": fg_int == hwnd_int,
        }

    def list_matching_windows(self) -> Dict[str, object]:
        pids = self._get_candidate_pids()
        target_titles = [t.lower() for t in self.targets]
        items: List[Dict[str, object]] = []

        EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

        @EnumWindowsProc
        def enum_windows_proc(hwnd, _lparam):
            if not bool(self.user32.IsWindowVisible(hwnd)):
                return True
            GW_OWNER = 4
            if self.user32.GetWindow(hwnd, GW_OWNER):
                return True

            length = self.user32.GetWindowTextLengthW(hwnd)
            if length <= 0:
                return True

            buffer = ctypes.create_unicode_buffer(length + 1)
            self.user32.GetWindowTextW(hwnd, buffer, length + 1)
            raw_title = buffer.value.strip()
            title_lower = raw_title.lower()
            if not title_lower:
                return True

            pid = self._get_window_pid(hwnd)
            # 没有检测到企微进程时，不做标题兜底匹配，避免误匹配（例如 Swagger UI/浏览器标签含 wecom）。
            if not pids:
                return True
            pid_match = bool(pids) and pid in pids
            title_match = any(t in title_lower for t in target_titles)
            if not (pid_match or title_match):
                return True

            hwnd_int = self._hwnd_to_int(hwnd)
            info = self.describe_window(hwnd_int)
            info["title_match"] = title_match
            info["pid_match"] = pid_match
            items.append(info)
            return True

        self.user32.EnumWindows.argtypes = [EnumWindowsProc, wintypes.LPARAM]
        self.user32.EnumWindows(enum_windows_proc, 0)

        return {
            "targets": list(self.targets),
            "process_names": list(self.process_names),
            "pids": sorted(pids),
            "windows": items,
        }

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
        candidates: List[Tuple[int, bool]] = []
        seen_titles: List[str] = []
        target_titles = [t.lower() for t in self.targets]
        pids = self._get_candidate_pids()

        EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

        @EnumWindowsProc
        def enum_windows_proc(hwnd, _lparam):
            # 过滤隐藏窗口/有 owner 的窗口，尽量拿到主窗口
            if not bool(self.user32.IsWindowVisible(hwnd)):
                return True
            GW_OWNER = 4
            if self.user32.GetWindow(hwnd, GW_OWNER):
                return True

            length = self.user32.GetWindowTextLengthW(hwnd)
            if length <= 0:
                return True

            buffer = ctypes.create_unicode_buffer(length + 1)
            self.user32.GetWindowTextW(hwnd, buffer, length + 1)
            raw_title = buffer.value.strip()
            title = raw_title.lower()
            if not title:
                return True

            if len(seen_titles) < 50:
                seen_titles.append(title)

            pid = self._get_window_pid(hwnd)
            # 没有检测到企微进程时，不做标题兜底匹配，避免误匹配（例如 Swagger UI/浏览器标签含 wecom）。
            if not pids:
                return True
            if pids and pid not in pids:
                return True

            for target in target_titles:
                if target in title:
                    candidates.append((self._hwnd_to_int(hwnd), True))
                    return True
            # pid 命中但标题没命中：也收集，后续会优先选择命中标题的
            if pids and pid in pids:
                candidates.append((self._hwnd_to_int(hwnd), False))
            return True

        self.user32.EnumWindows.argtypes = [EnumWindowsProc, wintypes.LPARAM]
        self.user32.EnumWindows(enum_windows_proc, 0)
        self._last_seen_titles = seen_titles
        if not candidates:
            return None, seen_titles

        def area_for(hwnd_int: int) -> int:
            rect = wintypes.RECT()
            if not bool(self.user32.GetWindowRect(wintypes.HWND(hwnd_int), ctypes.byref(rect))):
                return 0
            width = max(0, rect.right - rect.left)
            height = max(0, rect.bottom - rect.top)
            return width * height

        # 优先选标题命中的候选，其次选 pid-only 候选；同类里按面积选最大窗口
        candidates.sort(key=lambda c: (c[1], area_for(c[0])), reverse=True)
        best_hwnd, _matched = candidates[0]
        return best_hwnd, seen_titles

    def _force_foreground(self, hwnd: wintypes.HWND) -> Tuple[bool, Optional[str]]:
        current_tid = self.kernel32.GetCurrentThreadId()
        fg_hwnd = self.user32.GetForegroundWindow()
        fg_tid = self.user32.GetWindowThreadProcessId(fg_hwnd, None) if fg_hwnd else 0

        attached = False
        try:
            if fg_tid and fg_tid != current_tid:
                attached = bool(self.user32.AttachThreadInput(fg_tid, current_tid, True))

            self.user32.BringWindowToTop(hwnd)
            self.user32.SetActiveWindow(hwnd)
            if not self.user32.SetForegroundWindow(hwnd):
                return False, f"SetForegroundWindow failed ({self._last_error_message()})"
            sleep(0.05)
            now_fg = self.user32.GetForegroundWindow()
            now_fg_int = self._hwnd_to_int(now_fg)
            target_int = self._hwnd_to_int(hwnd)
            if now_fg_int and now_fg_int != target_int:
                now_title = self._get_window_title(now_fg)
                target_title = self._get_window_title(hwnd)
                return (
                    False,
                    "foreground verify failed "
                    f"target_hwnd={target_int} target_title={target_title!r} "
                    f"fg_hwnd={now_fg_int} fg_title={now_title!r}",
                )
            return True, None
        finally:
            if attached and fg_tid and fg_tid != current_tid:
                self.user32.AttachThreadInput(fg_tid, current_tid, False)

    def _get_exstyle(self, hwnd: wintypes.HWND) -> int:
        GWL_EXSTYLE = -20
        get_long_ptr = getattr(self.user32, "GetWindowLongPtrW", None)
        if get_long_ptr is not None:
            return int(get_long_ptr(hwnd, GWL_EXSTYLE))
        return int(self.user32.GetWindowLongW(hwnd, GWL_EXSTYLE))

    def activate_and_maximize(self, hwnd: int) -> Tuple[bool, Optional[str]]:
        """恢复窗口并最大化，然后激活到前台。"""
        if not bool(self.user32.IsWindow(wintypes.HWND(hwnd))):
            return False, "IsWindow=false (1400: 无效的窗口句柄)"

        try:
            SW_RESTORE = 9
            SW_SHOWMAXIMIZED = 3
            h = wintypes.HWND(hwnd)
            self.user32.ShowWindow(h, SW_RESTORE)
            self.user32.ShowWindow(h, SW_SHOWMAXIMIZED)
            sleep(0.05)

            ok, err = self._force_foreground(h)
            if not ok:
                return False, err

            sleep(0.05)
            if not bool(self.user32.IsZoomed(h)):
                title = self._get_window_title(h)
                return False, f"maximize verify failed hwnd={self._hwnd_to_int(h)} title={title!r}"

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

            sleep(0.05)
            WS_EX_TOPMOST = 0x00000008
            exstyle = self._get_exstyle(wintypes.HWND(hwnd))
            if (exstyle & WS_EX_TOPMOST) == 0:
                title = self._get_window_title(wintypes.HWND(hwnd))
                return False, f"topmost verify failed hwnd={hwnd} title={title!r} exstyle=0x{exstyle:x}"

            # 置顶后再尝试拉到前台并验证，避免“置顶成功但仍看不到变化”
            ok, err = self._force_foreground(wintypes.HWND(hwnd))
            if not ok:
                return False, err

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
        self.last_window_info: Optional[Dict[str, object]] = None

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

        describe = getattr(self.controller, "describe_window", None)
        if callable(describe):
            self.last_window_info = describe(hwnd)

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
                        if callable(describe):
                            self.last_window_info = describe(hwnd)
            reason = f"激活/最大化失败 hwnd={hwnd} error={activate_error or 'unknown'}"
            logger.error(reason)
            return False, None, reason

        if callable(describe):
            self.last_window_info = describe(hwnd)

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
                        if callable(describe):
                            self.last_window_info = describe(hwnd)
            reason = f"置顶失败 hwnd={hwnd} error={top_error or 'unknown'}"
            logger.error(reason)
            return False, None, reason

        if callable(describe):
            self.last_window_info = describe(hwnd)

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
