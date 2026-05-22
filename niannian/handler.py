"""念念 Handler — 包装 GenericAgentHandler，注入硬约束门禁
每次工具 dispatch 前检查 emergency_stop 和危险操作。
"""

import json
from pathlib import Path

# 延迟导入，避免循环依赖
def _get_ga():
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
    from ga import GenericAgentHandler
    return GenericAgentHandler

class NiannianHandler:
    """念念 Handler：在 GenericAgentHandler 外包装一层约束门禁
    不改 ga.py 源码，通过组合模式注入。
    """

    def __init__(self, parent, last_history=None, cwd='./temp'):
        GA = _get_ga()
        self._ga = GA(parent, last_history=last_history, cwd=cwd)
        self.parent = parent
        self._pending_confirm = {}  # {tool_name: args} 待确认的危险操作

    # 代理属性
    @property
    def working(self): return self._ga.working
    @working.setter
    def working(self, v): self._ga.working = v
    @property
    def cwd(self): return self._ga.cwd
    @cwd.setter
    def cwd(self, v): self._ga.cwd = v
    @property
    def current_turn(self): return self._ga.current_turn
    @current_turn.setter
    def current_turn(self, v): self._ga.current_turn = v
    @property
    def max_turns(self): return self._ga.max_turns
    @max_turns.setter
    def max_turns(self, v): self._ga.max_turns = v
    @property
    def history_info(self): return self._ga.history_info
    @property
    def code_stop_signal(self): return self._ga.code_stop_signal
    @property
    def _done_hooks(self): return getattr(self._ga, '_done_hooks', [])

    def turn_end_callback(self, *args, **kwargs):
        return self._ga.turn_end_callback(*args, **kwargs)

    def dispatch(self, tool_name, args, response, index=0, tool_num=1):
        """工具 dispatch — 前置注入念念约束"""
        from niannian.constraints import preflight, EMERGENCY_STOP

        # 1. 紧急中断检查
        if EMERGENCY_STOP:
            from agent_loop import StepOutcome
            yield "⏸ 主人触发'停'。\n"
            return StepOutcome({"stopped": True}, next_prompt="主人说了停。等待新指令。", should_exit=True)

        # 2. 危险操作需要确认
        check = preflight(tool_name, args)
        if not check["allowed"]:
            if check.get("require_confirm"):
                self._pending_confirm[tool_name] = args
                from agent_loop import StepOutcome
                yield check["reason"] + "\n"
                return StepOutcome(
                    {"pending_confirm": True, "tool": tool_name},
                    next_prompt=f"[系统] 工具 '{tool_name}' 需要主人确认后才能执行。请等待。"
                )
            else:
                from agent_loop import StepOutcome
                yield check["reason"] + "\n"
                return StepOutcome({"blocked": True}, next_prompt=check["reason"])

        # 3. 已确认的操作放行
        if tool_name in self._pending_confirm:
            del self._pending_confirm[tool_name]

        # 4. 委托给 GenericAgentHandler
        yield from self._ga.dispatch(tool_name, args, response, index=index, tool_num=tool_num)

    # 代理所有 do_* 方法到 _ga
    def __getattr__(self, name):
        return getattr(self._ga, name)
