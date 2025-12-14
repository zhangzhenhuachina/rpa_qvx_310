import unittest
from unittest.mock import patch

from src.env_check.env_checker import EnvChecker


class EnvCheckerTest(unittest.TestCase):
    # 正向：系统、分辨率、企微都符合，截图成功
    @patch("src.env_check.env_checker.capture_desktop", return_value="shot.png")
    @patch("src.env_check.env_checker.system_info.detect_enterprise_wechat_status")
    @patch("src.env_check.env_checker.system_info.get_screen_resolution")
    @patch("src.env_check.env_checker.system_info.get_os_label")
    def test_env_ok(
        self,
        mock_os_label,
        mock_resolution,
        mock_wechat_status,
        _mock_capture,
    ):
        mock_os_label.return_value = "win10"
        mock_resolution.return_value = (1920, 1080)
        mock_wechat_status.return_value = "已安装-启动"

        checker = EnvChecker(screenshot_path="artifacts/screenshots/locate.png")
        minimal_ready, desc = checker.check()

        self.assertTrue(minimal_ready)
        self.assertEqual(desc["操作系统类型"], "win10")
        self.assertEqual(desc["屏幕分辨率"], [1920, 1080])
        self.assertEqual(desc["企微是否启动"], "已安装-启动")
        self.assertEqual(desc["本次检查桌面截图位置"], "shot.png")

    # 负向：操作系统不支持，最小可用失败，截图失败
    @patch("src.env_check.env_checker.capture_desktop", return_value=None)
    @patch("src.env_check.env_checker.system_info.detect_enterprise_wechat_status")
    @patch("src.env_check.env_checker.system_info.get_screen_resolution")
    @patch("src.env_check.env_checker.system_info.get_os_label")
    def test_env_not_ok_when_os_unsupported(
        self,
        mock_os_label,
        mock_resolution,
        mock_wechat_status,
        _mock_capture,
    ):
        mock_os_label.return_value = "linux"
        mock_resolution.return_value = (1920, 1080)
        mock_wechat_status.return_value = "已安装-启动"

        checker = EnvChecker()
        minimal_ready, desc = checker.check()

        self.assertFalse(minimal_ready)
        self.assertEqual(desc["操作系统类型"], "linux")
        self.assertIsNone(desc["本次检查桌面截图位置"])
