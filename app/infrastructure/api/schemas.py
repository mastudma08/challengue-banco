from pydantic import BaseModel, ConfigDict

from app.domain.models import (
    Decision,
    DocumentationResult,
    Escalation,
    IdentityResult,
    OnboardingRequest,
    OnboardingStatus,
    OnboardingStep,
    RiskResult,
)


class StartOnboardingRequest(OnboardingRequest):
    """HTTP input contract. Domain validation is still applied after mapping."""


class OnboardingPublicResponse(BaseModel):
    """Deliberately excludes raw request PII, policy corpus text and internal audit trail."""

    model_config = ConfigDict(from_attributes=True)

    onboarding_id: str
    status: OnboardingStatus
    current_step: OnboardingStep
    decision: Decision | None
    identity: IdentityResult | None
    risk: RiskResult | None
    documentation: DocumentationResult | None
    escalation: Escalation | None
    customer_response: str | None
