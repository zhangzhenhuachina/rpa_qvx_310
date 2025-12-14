import logging
import threading
import time
from typing import Optional

from src.actions.max_and_top_action import WindowController
from src.core.runtime_context import RuntimeContext, runtime_context
from src.core.screen_size import get_screen_size_logical, get_screen_size_physical
from src.qvx_position.locator import PositionLocator


class WeComGuard:
    def __init__(
        self,
        *,
        interval_sec: float,
        locate_interval_sec: float,
        controller: Optional[WindowController] = None,
        locator: Optional[PositionLocator] = None,
        context: Optional[RuntimeContext] = None,
    ) -> None:
        self.interval_sec = max(0.2, float(interval_sec))
        self.locate_interval_sec = max(1.0, float(locate_interval_sec))
        self.controller = controller or WindowController()
        self.locator = locator or PositionLocator()
        self.context = context or runtime_context

        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, name="wecom-guard", daemon=True)
        self._thread.start()

    def stop(self, timeout_sec: float = 2.0) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=float(timeout_sec))

    def is_running(self) -> bool:
        return bool(self._thread) and self._thread.is_alive() and not self._stop_event.is_set()

    def update_config(self, *, interval_sec: Optional[float] = None, locate_interval_sec: Optional[float] = None) -> None:
        if interval_sec is not None:
            self.interval_sec = max(0.2, float(interval_sec))
        if locate_interval_sec is not None:
            self.locate_interval_sec = max(1.0, float(locate_interval_sec))

    def _run(self) -> None:
        logger = logging.getLogger(__name__)
        while not self._stop_event.is_set():
            start = time.time()
            try:
                self.tick(now=start)
            except Exception as exc:
                logger.exception("WeComGuard tick failed: %s", exc)
                self.context.set_last_error(f"{type(exc).__name__}: {exc}")
            elapsed = time.time() - start
            sleep_sec = max(0.0, self.interval_sec - elapsed)
            self._stop_event.wait(timeout=sleep_sec)

    def tick(self, *, now: Optional[float] = None) -> None:
        now_ts = float(now or time.time())
        logger = logging.getLogger(__name__)

        self.context.mark_guard_tick(tick_at=now_ts)
        self.context.update_screen_sizes(get_screen_size_physical(), get_screen_size_logical())

        hwnd, _seen_titles = self.controller.find_window()
        if not hwnd:
            self.context.set_last_error("wecom_window_not_found")
            return

        describe = getattr(self.controller, "describe_window", None)
        info = describe(hwnd) if callable(describe) else None
        need_maximize = bool(info) and not bool(info.get("is_zoomed"))
        need_topmost = bool(info) and not bool(info.get("is_topmost"))
        if info is None:
            need_maximize = True
            need_topmost = True

        if need_maximize:
            ok, err = self.controller.activate_and_maximize(hwnd)
            if not ok:
                message = f"activate_and_maximize_failed: {err or 'unknown'}"
                logger.warning(message)
                self.context.set_last_error(message)
            else:
                self.context.mark_max_top(at=now_ts)

        if need_topmost:
            ok, err = self.controller.set_topmost(hwnd)
            if not ok:
                message = f"set_topmost_failed: {err or 'unknown'}"
                logger.warning(message)
                self.context.set_last_error(message)
            else:
                self.context.mark_max_top(at=now_ts)

        snap = self.context.snapshot()
        last_locate_at = snap.meta.get("last_locate_at")
        should_locate = (
            snap.input_center_position is None
            or snap.send_button_position is None
            or not isinstance(last_locate_at, (int, float))
            or (now_ts - float(last_locate_at)) >= self.locate_interval_sec
        )
        if not should_locate:
            return

        input_loc = self.locator.locate("消息输入框")
        send_loc = self.locator.locate("消息发送按钮")

        input_center = None
        if input_loc.bbox:
            input_center = (
                int(input_loc.bbox.x + input_loc.bbox.width // 2),
                int(input_loc.bbox.y + input_loc.bbox.height // 2),
            )

        send_center = None
        if send_loc.bbox:
            send_center = (
                int(send_loc.bbox.x + send_loc.bbox.width // 2),
                int(send_loc.bbox.y + send_loc.bbox.height // 2),
            )

        if input_center or send_center:
            self.context.update_positions(
                input_center_position=input_center,
                send_button_position=send_center,
                located_at=now_ts,
            )
            self.context.set_last_error(None)
        else:
            self.context.set_last_error("locate_failed")
