import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from src.api.main import app


class ApiTest(unittest.TestCase):
    # 正向：环境检查返回 ok=True，detail 包含必要字段
    @patch("src.api.main.EnvChecker")
    def test_env_check_ok(self, mock_checker_cls):
        mock_checker = MagicMock()
        mock_checker.check.return_value = (True, {"操作系统类型": "win10"})
        mock_checker_cls.return_value = mock_checker

        client = TestClient(app)
        response = client.get("/health/env")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["ok"])
        self.assertEqual(data["detail"]["操作系统类型"], "win10")
        self.assertEqual(data["screenshot_url"], "/health/screenshot")

    @patch("src.api.main.capture_desktop")
    def test_health_screenshot_ok(self, mock_capture_desktop):
        fd, path = tempfile.mkstemp(suffix=".png")
        try:
            os.write(fd, b"\x89PNG\r\n\x1a\n")
            os.close(fd)

            mock_capture_desktop.return_value = path

            client = TestClient(app)
            response = client.get("/health/screenshot")

            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.headers["content-type"], "image/png")
            self.assertIn("no-store", response.headers.get("cache-control", ""))
            self.assertEqual(response.content[:8], b"\x89PNG\r\n\x1a\n")
        finally:
            try:
                os.remove(path)
            except FileNotFoundError:
                pass

    @patch("src.api.main.capture_desktop")
    def test_health_screenshot_fail(self, mock_capture_desktop):
        mock_capture_desktop.return_value = None
        client = TestClient(app)
        response = client.get("/health/screenshot")
        self.assertEqual(response.status_code, 500)
        self.assertIn("截图失败", response.text)

    # 正向：发送动作成功，返回 success 和截图路径
    @patch("src.api.main.SendMessageAction")
    def test_send_action_success(self, mock_action_cls):
        mock_action = MagicMock()
        mock_action.execute.return_value = (True, "after.png", None)
        mock_action.last_debug = {"ok": True}
        mock_action_cls.return_value = mock_action

        client = TestClient(app)
        response = client.post("/action/send")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["screenshot"], "after.png")
        self.assertTrue(data["debug"]["ok"])

    # 负向：发送动作失败，返回 500
    @patch("src.api.main.SendMessageAction")
    def test_send_action_fail(self, mock_action_cls):
        mock_action = MagicMock()
        mock_action.execute.return_value = (False, None, "发送失败")
        mock_action.last_debug = {"ok": False}
        mock_action_cls.return_value = mock_action

        client = TestClient(app)
        response = client.post("/action/send")

        self.assertEqual(response.status_code, 500)
        self.assertIn("发送失败", response.text)

    def test_guard_status_endpoint(self):
        client = TestClient(app)
        response = client.get("/debug/guard/status")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("running", data)

    def test_guard_start_stop_endpoints(self):
        client = TestClient(app)

        response = client.post("/debug/guard/start", json={"interval_sec": 0.5, "locate_interval_sec": 2.0})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])

        response = client.post("/debug/guard/stop")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])

    # 正向：最大化置顶成功，返回 success 与截图路径
    @patch("src.api.main.system_info.detect_enterprise_wechat_status", return_value="已安装-启动")
    @patch("src.api.main.MaxAndTopAction")
    def test_max_and_top_success(self, mock_action_cls, _mock_status):
        mock_action = MagicMock()
        mock_action.execute.return_value = (True, "max.png", None)
        mock_action.last_window_info = {"hwnd": 1}
        mock_action_cls.return_value = mock_action

        client = TestClient(app)
        response = client.post("/action/qvx_max_and_top")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["screenshot"], "max.png")
        self.assertEqual(data["window"]["hwnd"], 1)

    # 负向：最大化置顶失败，返回 500
    @patch("src.api.main.system_info.detect_enterprise_wechat_status", return_value="已安装-启动")
    @patch("src.api.main.MaxAndTopAction")
    def test_max_and_top_fail(self, mock_action_cls, _mock_status):
        mock_action = MagicMock()
        mock_action.execute.return_value = (False, None, "置顶失败 hwnd=1")
        mock_action_cls.return_value = mock_action

        client = TestClient(app)
        response = client.post("/action/qvx_max_and_top")

        self.assertEqual(response.status_code, 500)
        self.assertIn("置顶失败", response.text)

    @patch("src.api.main.system_info.detect_enterprise_wechat_status", return_value="已安装-未启动")
    def test_max_and_top_not_ready(self, _mock_status):
        client = TestClient(app)
        response = client.post("/action/qvx_max_and_top")
        self.assertEqual(response.status_code, 500)
        self.assertIn("企业微信未安装，或者未启动，需要手动启动", response.text)
