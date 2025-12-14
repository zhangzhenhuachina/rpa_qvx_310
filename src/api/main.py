import logging

import os
from datetime import datetime

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

from src.actions.max_and_top_action import MaxAndTopAction
from src.actions.send_message_action import SendMessageAction
from src.core import system_info
from src.core.screenshot import capture_desktop
from src.env_check.env_checker import EnvChecker
from src.actions.max_and_top_action import WindowController


def create_app() -> FastAPI:
    """创建 FastAPI 应用，并注册路由。"""
    app = FastAPI(title="WeCom RPA API", version="0.1.0")
    logger = logging.getLogger(__name__)

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
        filename = datetime.now().strftime("health_%Y%m%d_%H%M%S_%f.png")
        target_path = os.path.join("artifacts", "screenshots", filename)
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

    @app.post("/action/send")
    def send_message():
        """
        发送消息动作：
        - 成功时返回 success=True 与截图路径
        - 失败时抛出 HTTP 500
        """
        logger.info("Send message action started")
        success, screenshot = SendMessageAction().execute()
        if not success:
            logger.error("Send message action failed")
            raise HTTPException(status_code=500, detail="发送失败")
        logger.info("Send message action succeeded screenshot=%s", screenshot)
        return {"success": True, "screenshot": screenshot}



    return app


app = create_app()
