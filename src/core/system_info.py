import os
import platform
import subprocess
from typing import List, Optional, Tuple


def get_os_label() -> str:
    """返回简明操作系统标签，如 win10、win11、winserver2022。"""
    system_name = platform.system().lower()
    if system_name != "windows":
        return system_name

    release = platform.release().lower()
    version = platform.version().lower()
    if "10" in release and "2009" in version or "21h2" in version:
        return "win10"
    if "11" in release:
        return "win11"

    # Windows Server 版本的识别，保留版本号
    if "server" in release:
        return f"win{release}"

    return f"win{release}"


def get_screen_resolution() -> Optional[Tuple[int, int]]:
    """尝试获取屏幕分辨率，失败时返回 None。"""
    try:
        import ctypes  # type: ignore

        user32 = ctypes.windll.user32
        return user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
    except Exception:
        pass

    try:
        import pyautogui  # type: ignore

        size = pyautogui.size()
        return size.width, size.height
    except Exception:
        return None


def is_process_running(process_names: List[str]) -> bool:
    """检查任意给定进程名是否存在。"""
    if not process_names:
        return False

    try:
        tasklist = subprocess.run(
            ["tasklist"],
            capture_output=True,
            text=True,
            check=False,
        )
    except Exception:
        return False

    output = tasklist.stdout.lower()
    return any(name.lower() in output for name in process_names)


def detect_enterprise_wechat_status() -> str:
    """
    返回企微状态：
    - 已安装-启动
    - 已安装-未启动
    - 未安装
    """
    process_names = ["wxwork.exe", "wecom.exe", "wechatwork.exe"]
    running = is_process_running(process_names)

    install_paths = [
        os.path.expandvars(r"%ProgramFiles%\\WXWork"),
        os.path.expandvars(r"%ProgramFiles(x86)%\\WXWork"),
        os.path.expandvars(r"%LOCALAPPDATA%\\WXWork"),
        os.path.expandvars(r"%ProgramFiles%\\WeCom"),
        os.path.expandvars(r"%ProgramFiles(x86)%\\WeCom"),
    ]

    installed = any(os.path.exists(path) for path in install_paths)

    if installed and running:
        return "已安装-启动"
    if installed:
        return "已安装-未启动"
    return "未安装"
