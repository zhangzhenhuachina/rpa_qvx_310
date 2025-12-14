import logging

import os
from datetime import datetime
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from src.actions.max_and_top_action import MaxAndTopAction
from src.actions.send_message_action import SendMessageAction
from src.core import system_info
from src.core.runtime_context import runtime_context
from src.core.screenshot import capture_desktop
from src.daemon.wecom_guard import WeComGuard
from src.env_check.env_checker import EnvChecker
from src.actions.max_and_top_action import WindowController
from src.api.logging_config import setup_logging
from src.settings import WECOM_GUARD_ENABLED, WECOM_GUARD_INTERVAL_SEC, WECOM_GUARD_LOCATE_INTERVAL_SEC


class GuardConfig(BaseModel):
    interval_sec: float | None = None
    locate_interval_sec: float | None = None


def create_app() -> FastAPI:
    """创建 FastAPI 应用，并注册路由。"""
    setup_logging()
    app = FastAPI(title="WeCom RPA API", version="0.1.0")
    logger = logging.getLogger(__name__)

    @app.on_event("startup")
    def startup():
        if not WECOM_GUARD_ENABLED:
            return
        guard = WeComGuard(
            interval_sec=WECOM_GUARD_INTERVAL_SEC,
            locate_interval_sec=WECOM_GUARD_LOCATE_INTERVAL_SEC,
            context=runtime_context,
        )
        guard.start()
        app.state.wecom_guard = guard
        logger.info(
            "WeComGuard started interval_sec=%s locate_interval_sec=%s",
            WECOM_GUARD_INTERVAL_SEC,
            WECOM_GUARD_LOCATE_INTERVAL_SEC,
        )

    @app.on_event("shutdown")
    def shutdown():
        guard = getattr(app.state, "wecom_guard", None)
        if not guard:
            return
        guard.stop()
        logger.info("WeComGuard stopped")

    @app.middleware("http")
    async def add_request_id_and_log(request, call_next):
        request_id = request.headers.get("X-Request-ID") or str(uuid4())
        request.state.request_id = request_id
        logger.info(
            "request start id=%s method=%s path=%s client=%s",
            request_id,
            request.method,
            request.url.path,
            request.client.host if request.client else None,
        )
        try:
            response = await call_next(request)
        except Exception:
            logger.exception("request error id=%s method=%s path=%s", request_id, request.method, request.url.path)
            raise
        response.headers["X-Request-ID"] = request_id
        logger.info(
            "request end id=%s status=%s method=%s path=%s",
            request_id,
            getattr(response, "status_code", None),
            request.method,
            request.url.path,
        )
        return response

    @app.get("/health/env")
    def env_check():
        """
        环境检查：
        - 返回 ok 是否满足最小可用
        - detail 包含分辨率、操作系统、企微状态、截图位置
        """
        logger.info("Run health env check")
        ok, detail = EnvChecker().check()
        logger.info("Health env check result ok=%s detail_keys=%s", ok, list(detail.keys()))
        return {"ok": ok, "detail": detail, "screenshot_url": "/health/screenshot"}

    @app.get("/health/screenshot")
    def health_screenshot():
        """
        返回当前桌面截图（image/png），用于在浏览器里查看“最实时”的截图。
        注意：该截图发生在本请求处理期间，并通过禁止缓存头确保每次刷新都拿到新图。
        """
        target_path = os.path.join("artifacts", "screenshots", "health.png")
        screenshot_path = capture_desktop(target_path)
        if not screenshot_path:
            raise HTTPException(status_code=500, detail="截图失败")

        return FileResponse(
            screenshot_path,
            media_type="image/png",
            filename="desktop.png",
            headers={
                "Cache-Control": "no-store, max-age=0",
                "Pragma": "no-cache",
            },
        )
    

    @app.post("/action/qvx_max_and_top")
    def max_and_top():
        """
        企业微信最大化并置顶：
        - 成功时返回 success=True 与截图路径
        - 失败时抛出 HTTP 500
        """
        logger.info("Max and top action started")
        status = system_info.detect_enterprise_wechat_status()
        if status != "已安装-启动":
            logger.error("Enterprise WeChat not ready status=%s", status)
            raise HTTPException(
                status_code=500,
                detail="企业微信未安装，或者未启动，需要手动启动",
            )

        action = MaxAndTopAction()
        success, screenshot, error = action.execute()
        if not success:
            logger.error("Max and top action failed error=%s", error)
            raise HTTPException(status_code=500, detail=error or "置顶失败")
        logger.info("Max and top action succeeded screenshot=%s", screenshot)
        return {"success": True, "screenshot": screenshot, "window": action.last_window_info}

    @app.get("/debug/windows/wecom")
    def debug_wecom_windows():
        """调试：列出当前识别到的企微窗口候选（hwnd/title/pid/rect/是否前台/最大化/置顶）。"""
        return WindowController().list_matching_windows()

    @app.get("/debug/context")
    def debug_context():
        return runtime_context.snapshot().__dict__

    @app.get("/debug/guard/status")
    def guard_status():
        guard = getattr(app.state, "wecom_guard", None)
        return {
            "enabled": WECOM_GUARD_ENABLED,
            "running": bool(guard) and guard.is_running(),
            "interval_sec": getattr(guard, "interval_sec", None),
            "locate_interval_sec": getattr(guard, "locate_interval_sec", None),
        }

    @app.post("/debug/guard/start")
    def guard_start(config: GuardConfig = GuardConfig()):
        guard = getattr(app.state, "wecom_guard", None)
        if not guard:
            guard = WeComGuard(
                interval_sec=WECOM_GUARD_INTERVAL_SEC,
                locate_interval_sec=WECOM_GUARD_LOCATE_INTERVAL_SEC,
                context=runtime_context,
            )
            app.state.wecom_guard = guard
        guard.update_config(interval_sec=config.interval_sec, locate_interval_sec=config.locate_interval_sec)
        guard.start()
        return {"success": True, "running": guard.is_running()}

    @app.post("/debug/guard/stop")
    def guard_stop():
        guard = getattr(app.state, "wecom_guard", None)
        if not guard:
            return {"success": True, "running": False}
        guard.stop()
        return {"success": True, "running": guard.is_running()}

    @app.post("/action/send")
    def send_message():
        """
        发送消息动作：
        - 成功时返回 success=True 与截图路径
        - 失败时抛出 HTTP 500
        """
        logger.info("Send message action started")
        action = SendMessageAction(context=runtime_context)
        success, screenshot, error = action.execute()
        if not success:
            logger.error("Send message action failed error=%s debug=%s", error, action.last_debug)
            raise HTTPException(
                status_code=500,
                detail={"message": error or "发送失败", "debug": action.last_debug},
            )
        logger.info("Send message action succeeded screenshot=%s", screenshot)
        return {"success": True, "screenshot": screenshot, "debug": action.last_debug}



    return app


app = create_app()
