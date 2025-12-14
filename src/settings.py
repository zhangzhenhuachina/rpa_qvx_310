import os

# 发送消息后截图保存位置，支持通过环境变量覆盖
SCREEN_SEND_MSG_AFTER = os.getenv(
    "SCREEN_SEND_MSG_AFTER",
    os.path.join("artifacts", "send_message"),
)

# 最大化置顶后的截图保存位置，支持通过环境变量覆盖
SCREEN_MAX_AND_TOP = os.getenv(
    "SCREEN_MAX_AND_TOP",
    os.path.join("artifacts", "max_and_top"),
)

# 模板根目录
TEMPLATE_ROOT = os.getenv("TEMPLATE_ROOT", "templates")


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() not in {"0", "false", "no", "off"}


WECOM_GUARD_ENABLED = _env_bool("WECOM_GUARD_ENABLED", True)
WECOM_GUARD_INTERVAL_SEC = float(os.getenv("WECOM_GUARD_INTERVAL_SEC", "5.0"))
WECOM_GUARD_LOCATE_INTERVAL_SEC = float(os.getenv("WECOM_GUARD_LOCATE_INTERVAL_SEC", "15.0"))
