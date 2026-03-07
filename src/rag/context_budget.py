"""
上下文预算管理器：控制送入 LLM 的 token 总量。

职责：
- 定义 token 预算上限
- 按优先级分配 token 配额（系统提示、历史对话、检索上下文、用户输入）
- 实时追踪 token 消耗
"""

from dataclasses import dataclass, field
from typing import Dict


@dataclass
class BudgetAllocation:
    """token 预算分配方案"""
    system_prompt: int = 500       # 系统提示词配额
    conversation_history: int = 1000  # 历史对话配额
    retrieval_context: int = 2000  # 检索上下文配额（核心）
    user_input: int = 500          # 用户当前输入配额
    safety_margin: int = 200       # 安全余量

    @property
    def total(self) -> int:
        return (
            self.system_prompt
            + self.conversation_history
            + self.retrieval_context
            + self.user_input
            + self.safety_margin
        )


class ContextBudgetManager:
    """
    上下文预算管理器

    管理 LLM 调用中的 token 分配，确保检索内容不超出模型窗口。
    """

    def __init__(
        self,
        max_total_tokens: int = 4096,
        allocation: BudgetAllocation = None,
    ):
        self.max_total_tokens = max_total_tokens
        self.allocation = allocation or BudgetAllocation()
        self._usage: Dict[str, int] = {
            "system_prompt": 0,
            "conversation_history": 0,
            "retrieval_context": 0,
            "user_input": 0,
        }

    def get_retrieval_budget(self) -> int:
        """获取检索上下文可用的 token 预算"""
        used_by_others = (
            self._usage["system_prompt"]
            + self._usage["conversation_history"]
            + self._usage["user_input"]
        )
        available = self.max_total_tokens - used_by_others - self.allocation.safety_margin
        return min(available, self.allocation.retrieval_context)

    def record_usage(self, category: str, tokens: int):
        """记录某类内容的 token 消耗"""
        if category in self._usage:
            self._usage[category] = tokens

    def remaining_tokens(self) -> int:
        """剩余可用 token 数"""
        used = sum(self._usage.values())
        return max(self.max_total_tokens - used - self.allocation.safety_margin, 0)

    def is_over_budget(self) -> bool:
        """是否已超出预算"""
        return self.remaining_tokens() <= 0

    def summary(self) -> Dict[str, int]:
        """返回预算使用摘要"""
        return {
            "max_total": self.max_total_tokens,
            "used": sum(self._usage.values()),
            "remaining": self.remaining_tokens(),
            **{f"used_{k}": v for k, v in self._usage.items()},
        }
