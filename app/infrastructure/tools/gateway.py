from collections.abc import Callable
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.application.ports.tool_gateway import ToolGatewayPort
from app.infrastructure.tools.mocks import MockExternalTools


class ToolPermissionError(PermissionError):
    pass


class ToolInputValidationError(ValueError):
    pass


class StrictArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")


class VerifyIdentityArgs(StrictArgs):
    document_id: str = Field(pattern=r"^\d{10}$")


class RiskArgs(StrictArgs):
    name: str = Field(min_length=2, max_length=120)
    document_id: str = Field(pattern=r"^\d{10}$")


class ClientData(StrictArgs):
    prospect_name: str = Field(min_length=2, max_length=120)
    document_id: str = Field(pattern=r"^\d{10}$")


class DocumentationArgs(StrictArgs):
    product: Literal["cuenta_ahorros", "cuenta_corriente"]
    client_data: ClientData


class ToolGateway(ToolGatewayPort):
    """Policy enforcement point: least privilege + strict argument schemas."""

    _permissions: dict[str, set[str]] = {
        "identity_agent": {"verify_identity"},
        "risk_agent": {"check_risk_lists"},
        "documentation_agent": {"prepare_documentation"},
        "response_agent": set(),
    }

    def __init__(self, tools: MockExternalTools):
        self._tools: dict[str, Callable[..., Any]] = {
            "verify_identity": tools.verify_identity,
            "check_risk_lists": tools.check_risk_lists,
            "prepare_documentation": tools.prepare_documentation,
        }
        self._schemas: dict[str, type[StrictArgs]] = {
            "verify_identity": VerifyIdentityArgs,
            "check_risk_lists": RiskArgs,
            "prepare_documentation": DocumentationArgs,
        }

    def execute(self, agent_id: str, tool_name: str, **kwargs: Any) -> Any:
        allowed = self._permissions.get(agent_id, set())
        if tool_name not in allowed:
            raise ToolPermissionError(
                f"agent '{agent_id}' is not allowed to use tool '{tool_name}'"
            )
        tool = self._tools.get(tool_name)
        schema = self._schemas.get(tool_name)
        if tool is None or schema is None:
            raise KeyError(f"unknown tool '{tool_name}'")
        try:
            validated = schema.model_validate(kwargs).model_dump()
        except Exception as exc:
            raise ToolInputValidationError(f"invalid arguments for tool '{tool_name}'") from exc
        return tool(**validated)
