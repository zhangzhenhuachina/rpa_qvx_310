from typing import Dict, Optional, Tuple

from src.core import system_info
from src.core.screenshot import capture_desktop


SUPPORTED_OS_PREFIX = ("win10", "win11", "winserver")


class EnvChecker:
    """环境检查器，负责判定最小可用环境是否满足。"""

    def __init__(self, screenshot_path: Optional[str] = None) -> None:
        self.screenshot_path = screenshot_path

    def check(self) -> Tuple[bool, Dict[str, object]]:
        os_label = system_info.get_os_label()
        screen_resolution = system_info.get_screen_resolution()
        wechat_status = system_info.detect_enterprise_wechat_status()
        screenshot_location = capture_desktop(self.screenshot_path) if self.screenshot_path else None

        os_supported = self._is_os_supported(os_label)
        wechat_ok = wechat_status == "已安装-启动"
        screen_ok = screen_resolution is not None

        minimal_ready = os_supported and wechat_ok and screen_ok

        description = self._build_description(
            screen_resolution,
            os_label,
            wechat_status,
            screenshot_location,
        )

        return minimal_ready, description

    def _is_os_supported(self, os_label: str) -> bool:
        lower_label = os_label.lower()
        return lower_label.startswith(SUPPORTED_OS_PREFIX)

    def _build_description(
        self,
        screen_resolution: Optional[Tuple[int, int]],
        os_label: str,
        wechat_status: str,
        screenshot_location: Optional[str],
    ) -> Dict[str, object]:
        resolution_value = None
        if screen_resolution:
            resolution_value = [screen_resolution[0], screen_resolution[1]]

        return {
            "屏幕分辨率": resolution_value,
            "操作系统类型": os_label,
            "企微是否启动": wechat_status,
            "本次检查桌面截图位置": screenshot_location,
        }
