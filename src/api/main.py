import logging

from fastapi import FastAPI, HTTPException

from src.actions.max_and_top_action import MaxAndTopAction
from src.actions.send_message_action import SendMessageAction
from src.env_check.env_checker import EnvChecker


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
        return {"ok": ok, "detail": detail}
    

    @app.post("/action/qvx_max_and_top")
    def max_and_top():
        """
        企业微信最大化并置顶：
        - 成功时返回 success=True 与截图路径
        - 失败时抛出 HTTP 500
        """
        logger.info("Max and top action started")
        success, screenshot = MaxAndTopAction().execute()
        if not success:
            logger.error("Max and top action failed")
            raise HTTPException(status_code=500, detail="置顶失败")
        logger.info("Max and top action succeeded screenshot=%s", screenshot)
        return {"success": True, "screenshot": screenshot}

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
