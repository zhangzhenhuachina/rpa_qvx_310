from typing import Optional, Tuple


def get_screen_size_logical() -> Optional[Tuple[int, int]]:
    try:
        import ctypes  # type: ignore

        user32 = ctypes.windll.user32
        return int(user32.GetSystemMetrics(0)), int(user32.GetSystemMetrics(1))
    except Exception:
        pass

    try:
        import pyautogui  # type: ignore

        size = pyautogui.size()
        return int(size.width), int(size.height)
    except Exception:
        return None


def get_screen_size_physical() -> Optional[Tuple[int, int]]:
    try:
        import ctypes  # type: ignore

        user32 = ctypes.windll.user32
        gdi32 = ctypes.windll.gdi32
        hdc = user32.GetDC(0)
        if not hdc:
            return None
        try:
            DESKTOPVERTRES = 117
            DESKTOPHORZRES = 118
            width = int(gdi32.GetDeviceCaps(hdc, DESKTOPHORZRES))
            height = int(gdi32.GetDeviceCaps(hdc, DESKTOPVERTRES))
            if width > 0 and height > 0:
                return width, height
        finally:
            user32.ReleaseDC(0, hdc)
    except Exception:
        return None
    return None

