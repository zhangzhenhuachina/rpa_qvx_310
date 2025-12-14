import os
import logging
import threading
from typing import Optional


CAPTURE_LOCK = threading.RLock()


def _default_path() -> str:
    return os.path.join("artifacts", "screenshots", "locate.png")


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

    logger = logging.getLogger(__name__)
    base, ext = os.path.splitext(target_path)
    tmp_path = f"{base}.tmp{ext or '.png'}"
    errors: list[str] = []
    try:
        import pyautogui  # type: ignore

        with CAPTURE_LOCK:
            screenshot = pyautogui.screenshot()
            screenshot.save(tmp_path)
            os.replace(tmp_path, target_path)
            return target_path
    except Exception as exc:
        errors.append(f"pyautogui: {type(exc).__name__}: {exc}")

    try:
        from PIL import ImageGrab  # type: ignore

        with CAPTURE_LOCK:
            image = ImageGrab.grab()
            image.save(tmp_path)
            os.replace(tmp_path, target_path)
            return target_path
    except Exception as exc:
        errors.append(f"ImageGrab: {type(exc).__name__}: {exc}")
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:
            pass
        logger.error("capture_desktop failed target_path=%s errors=%s", target_path, errors)
        return None
