"""念念约束层 — 不可变安全门禁
注入 GenericAgent 的 tool dispatch 前执行。
由 SOUL/RULES/USER 配置文件驱动，Agent 自身不可修改。
"""

import json
from pathlib import Path

CONFIG_PATH = Path(__file__).parent / "config.json"

# ═══ 全局状态 ═══
EMERGENCY_STOP = False  # 主人说"停"后置位，所有工具执行前检查

def load_config():
    if CONFIG_PATH.exists():
        return json.loads(CONFIG_PATH.read_text())
    return {}

def emergency_stop():
    """触发紧急中断"""
    global EMERGENCY_STOP
    EMERGENCY_STOP = True

def reset_stop():
    """重置中断状态"""
    global EMERGENCY_STOP
    EMERGENCY_STOP = False

# ═══ 规则检测函数 ═══

def is_stop_command(text: str) -> bool:
    """RULES: 检测是否触发'停'"""
    stops = ("停", "stop", "中止", "取消", "emergency")
    return text.strip().lower() in stops

def is_confirm_command(text: str) -> bool:
    """RULES 规则0: 检测是否是明确的执行确认"""
    confirms = ("试", "修", "查", "改", "干", "执行", "确认", "搞", "做", "跑",
                "yes", "y", "ok", "go", "do", "run", "可以", "行", "好", "对")
    t = text.strip().lower()
    return any(t.startswith(c) or t == c for c in confirms)

def is_dangerous_tool(tool_name: str, args: dict) -> bool:
    """SOUL: 检测工具调用是否危险（需要主人确认）"""
    dangerous_tools = {
        "file_write", "file_patch", "code_run", "web_execute_js",
    }
    if tool_name in dangerous_tools:
        return True
    # 检查文件操作是否涉及系统路径
    path = args.get("path", "")
    dangerous_paths = ("/etc/", "/boot/", "~/.ssh/", "~/.config/", "config.yaml", ".env")
    if any(p in path for p in dangerous_paths):
        return True
    # 检查命令是否危险
    cmd = args.get("script", "") or args.get("command", "")
    dangerous_cmds = ("rm -rf", "sudo", "chmod", "systemctl", "reboot", "shutdown")
    if any(c in cmd for c in dangerous_cmds):
        return True
    return False

# ═══ 前置检查（注入 dispatch 前） ═══

def preflight(tool_name: str, args: dict, pending_confirmation: bool = False) -> dict:
    """工具执行前的前置检查。返回:
    {"allowed": True/False, "reason": "...", "require_confirm": True/False}
    """
    global EMERGENCY_STOP

    # 1. 最高优先：紧急中断
    if EMERGENCY_STOP:
        return {"allowed": False, "reason": "⏸ 主人触发了'停'，所有操作已中断。"}

    # 2. 危险操作检查
    if is_dangerous_tool(tool_name, args):
        if not pending_confirmation:
            return {"allowed": False, "reason": f"⚠️ '{tool_name}' 是危险操作，需主人确认。", "require_confirm": True}

    return {"allowed": True}
