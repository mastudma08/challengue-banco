from app.application.ports.tool_gateway import ToolGatewayPort
from app.domain.models import IdentityResult, OnboardingRequest


class IdentityAgent:
    agent_id = "identity_agent"

    def __init__(self, gateway: ToolGatewayPort):
        self.gateway = gateway

    def run(self, request: OnboardingRequest) -> IdentityResult:
        raw = self.gateway.execute(
            self.agent_id,
            "verify_identity",
            document_id=request.document_id,
        )
        return IdentityResult.model_validate(raw)
