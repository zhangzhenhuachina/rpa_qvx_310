import threading
import time
from dataclasses import dataclass
from typing import Dict, Optional, Tuple


Point = Tuple[int, int]
Size = Tuple[int, int]


@dataclass(frozen=True)
class RuntimeContextSnapshot:
    p_screen_size: Optional[Size]
    l_screen_size: Optional[Size]
    input_center_position: Optional[Point]
    send_button_position: Optional[Point]
    meta: Dict[str, object]


class RuntimeContext:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._p_screen_size: Optional[Size] = None
        self._l_screen_size: Optional[Size] = None
        self._input_center_position: Optional[Point] = None
        self._send_button_position: Optional[Point] = None
        self._meta: Dict[str, object] = {
            "created_at": time.time(),
            "updated_at": None,
            "last_guard_tick_at": None,
            "last_locate_at": None,
            "last_max_top_at": None,
            "last_locate_screenshot": None,
            "last_locate_annotated_screenshot": None,
            "last_error": None,
        }

    def snapshot(self) -> RuntimeContextSnapshot:
        with self._lock:
            return RuntimeContextSnapshot(
                p_screen_size=self._p_screen_size,
                l_screen_size=self._l_screen_size,
                input_center_position=self._input_center_position,
                send_button_position=self._send_button_position,
                meta=dict(self._meta),
            )

    def update_screen_sizes(self, p_screen_size: Optional[Size], l_screen_size: Optional[Size]) -> None:
        with self._lock:
            if p_screen_size:
                self._p_screen_size = p_screen_size
            if l_screen_size:
                self._l_screen_size = l_screen_size
            self._meta["updated_at"] = time.time()

    def update_positions(
        self,
        input_center_position: Optional[Point] = None,
        send_button_position: Optional[Point] = None,
        *,
        located_at: Optional[float] = None,
        locate_screenshot: Optional[str] = None,
        locate_annotated_screenshot: Optional[str] = None,
    ) -> None:
        with self._lock:
            if input_center_position:
                self._input_center_position = input_center_position
            if send_button_position:
                self._send_button_position = send_button_position
            if located_at is not None:
                self._meta["last_locate_at"] = float(located_at)
            if locate_screenshot is not None:
                self._meta["last_locate_screenshot"] = locate_screenshot
            if locate_annotated_screenshot is not None:
                self._meta["last_locate_annotated_screenshot"] = locate_annotated_screenshot
            self._meta["updated_at"] = time.time()

    def mark_guard_tick(self, *, tick_at: Optional[float] = None) -> None:
        with self._lock:
            self._meta["last_guard_tick_at"] = float(tick_at or time.time())
            self._meta["updated_at"] = time.time()

    def mark_max_top(self, *, at: Optional[float] = None) -> None:
        with self._lock:
            self._meta["last_max_top_at"] = float(at or time.time())
            self._meta["updated_at"] = time.time()

    def set_last_error(self, message: Optional[str]) -> None:
        with self._lock:
            self._meta["last_error"] = message
            self._meta["updated_at"] = time.time()


runtime_context = RuntimeContext()
