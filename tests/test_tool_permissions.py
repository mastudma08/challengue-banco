import pytest

from app.infrastructure.tools.gateway import (
    ToolGateway,
    ToolInputValidationError,
    ToolPermissionError,
)
from app.infrastructure.tools.mocks import MockExternalTools


def test_agent_cannot_call_unapproved_tool():
    gateway = ToolGateway(MockExternalTools())
    with pytest.raises(ToolPermissionError):
        gateway.execute(
            "identity_agent",
            "check_risk_lists",
            name="Juan Perez",
            document_id="1712345678",
        )


def test_tool_gateway_rejects_extra_arguments():
    gateway = ToolGateway(MockExternalTools())
    with pytest.raises(ToolInputValidationError):
        gateway.execute(
            "identity_agent",
            "verify_identity",
            document_id="1712345678",
            force_verified=True,
        )
