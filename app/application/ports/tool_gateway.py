from abc import ABC, abstractmethod
from typing import Any


class ToolGatewayPort(ABC):
    @abstractmethod
    def execute(self, agent_id: str, tool_name: str, **kwargs: Any) -> Any:
        raise NotImplementedError
