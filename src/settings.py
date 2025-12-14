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
