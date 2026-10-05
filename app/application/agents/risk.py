from app.application.ports.tool_gateway import ToolGatewayPort
from app.domain.models import OnboardingRequest, RiskResult


class RiskAgent:
    agent_id = "risk_agent"

    def __init__(self, gateway: ToolGatewayPort):
        self.gateway = gateway

    def run(self, request: OnboardingRequest) -> RiskResult:
        raw = self.gateway.execute(
            self.agent_id,
            "check_risk_lists",
            name=request.prospect_name,
            document_id=request.document_id,
        )
        return RiskResult.model_validate(raw)
