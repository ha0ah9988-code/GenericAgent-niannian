"""念念 — GenericAgent 硬约束集成层
不改动 GenericAgent 源码，通过组合模式注入 SOUL/RULES/USER 门禁。
"""

from niannian.constraints import (
    EMERGENCY_STOP, emergency_stop, reset_stop,
    is_stop_command, is_confirm_command, is_dangerous_tool,
    preflight, load_config,
)
from niannian.handler import NiannianHandler

__version__ = "0.2.0"
