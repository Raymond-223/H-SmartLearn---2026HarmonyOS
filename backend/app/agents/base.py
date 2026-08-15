"""Shared agent contract.

Agents are pure workflow workers: they read WorkflowState and return AgentResult.
They never write to the database directly.
"""

from abc import ABC, abstractmethod
from typing import Any, Optional
from pydantic import BaseModel, Field


class AgentResult(BaseModel):
    status: str = "success"
    output: dict = Field(default_factory=dict)
    confidence: Optional[float] = None
    next_action: Optional[str] = None
    warnings: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    summary: str = ""


class BaseAgent(ABC):
    agent_type: str = "base"

    @abstractmethod
    async def run(self, context: Any, agent_input: dict) -> AgentResult:
        ...
