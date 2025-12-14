import os
from datetime import datetime
from typing import Optional


def _default_path() -> str:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return os.path.join("artifacts", "screenshots", f"desktop_{timestamp}.png")


def ensure_folder(path: str) -> None:
    folder = os.path.dirname(path)
    if folder:
        os.makedirs(folder, exist_ok=True)


def capture_desktop(path: Optional[str] = None) -> Optional[str]:
    """
    截取桌面截图，返回保存路径，失败时返回 None。
    优先使用 pyautogui，其次尝试 PIL.ImageGrab。
    """
    target_path = path or _default_path()
    ensure_folder(target_path)

    try:
        import pyautogui  # type: ignore

        screenshot = pyautogui.screenshot()
        screenshot.save(target_path)
        return target_path
    except Exception:
        pass

    try:
        from PIL import ImageGrab  # type: ignore

        image = ImageGrab.grab()
        image.save(target_path)
        return target_path
    except Exception:
        return None
