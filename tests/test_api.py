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

    # 正向：发送动作成功，返回 success 和截图路径
    @patch("src.api.main.SendMessageAction")
    def test_send_action_success(self, mock_action_cls):
        mock_action = MagicMock()
        mock_action.execute.return_value = (True, "after.png")
        mock_action_cls.return_value = mock_action

        client = TestClient(app)
        response = client.post("/action/send")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["screenshot"], "after.png")

    # 负向：发送动作失败，返回 500
    @patch("src.api.main.SendMessageAction")
    def test_send_action_fail(self, mock_action_cls):
        mock_action = MagicMock()
        mock_action.execute.return_value = (False, None)
        mock_action_cls.return_value = mock_action

        client = TestClient(app)
        response = client.post("/action/send")

        self.assertEqual(response.status_code, 500)
        self.assertIn("发送失败", response.text)

    # 正向：最大化置顶成功，返回 success 与截图路径
    @patch("src.api.main.MaxAndTopAction")
    def test_max_and_top_success(self, mock_action_cls):
        mock_action = MagicMock()
        mock_action.execute.return_value = (True, "max.png")
        mock_action_cls.return_value = mock_action

        client = TestClient(app)
        response = client.post("/action/qvx_max_and_top")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["screenshot"], "max.png")

    # 负向：最大化置顶失败，返回 500
    @patch("src.api.main.MaxAndTopAction")
    def test_max_and_top_fail(self, mock_action_cls):
        mock_action = MagicMock()
        mock_action.execute.return_value = (False, None)
        mock_action_cls.return_value = mock_action

        client = TestClient(app)
        response = client.post("/action/qvx_max_and_top")

        self.assertEqual(response.status_code, 500)
        self.assertIn("置顶失败", response.text)
