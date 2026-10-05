from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class OnboardingStatus(StrEnum):
    RECEIVED = "received"
    IN_PROGRESS = "in_progress"
    APPROVED = "approved"
    REJECTED = "rejected"
    MANUAL_REVIEW = "manual_review"


class OnboardingStep(StrEnum):
    RECEIVED = "received"
    VERIFY_IDENTITY = "verify_identity"
    CHECK_RISK = "check_risk"
    RETRIEVE_POLICY = "retrieve_policy"
    PREPARE_DOCUMENTATION = "prepare_documentation"
    GENERATE_RESPONSE = "generate_response"
    COMPLETED = "completed"


class Decision(StrEnum):
    APPROVED = "approved"
    REJECTED = "rejected"
    MANUAL_REVIEW = "manual_review"


class OnboardingRequest(BaseModel):
    """Authoritative backend contract. Front-end validation is never trusted."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    prospect_name: str = Field(min_length=2, max_length=120)
    document_id: str = Field(pattern=r"^\d{10}$")
    product: Literal["cuenta_ahorros", "cuenta_corriente"]

    @field_validator("prospect_name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        allowed_punctuation = {" ", "'", "-", "."}
        if not all(ch.isalpha() or ch in allowed_punctuation for ch in value):
            raise ValueError("prospect_name contains unsupported characters")
        if not any(ch.isalpha() for ch in value):
            raise ValueError("prospect_name must contain letters")
        return " ".join(value.split())


class IdentityResult(BaseModel):
    verified: bool
    confidence: float = Field(ge=0.0, le=1.0)


class RiskResult(BaseModel):
    risk_level: Literal["low", "medium", "high"]
    matches: list[dict[str, Any] | str] = Field(default_factory=list)


class DocumentationResult(BaseModel):
    required_documents: list[str] = Field(default_factory=list)


class PolicyEvidence(BaseModel):
    source: str
    section: str
    content: str
    score: float = Field(ge=0.0, le=1.0)


class DocumentationAgentOutput(BaseModel):
    documentation: DocumentationResult
    policy_evidence: list[PolicyEvidence] = Field(default_factory=list)


class CustomerResponseOutput(BaseModel):
    text: str
    used_llm: bool
    fallback_reason: str | None = None


class Escalation(BaseModel):
    reason_code: str
    stage: OnboardingStep
    message: str
    recommended_action: str


class AuditEvent(BaseModel):
    at: datetime = Field(default_factory=utc_now)
    step: OnboardingStep
    event: str
    details: dict[str, Any] = Field(default_factory=dict)


class OnboardingState(BaseModel):
    onboarding_id: str = Field(default_factory=lambda: str(uuid4()))
    request: OnboardingRequest
    status: OnboardingStatus = OnboardingStatus.RECEIVED
    current_step: OnboardingStep = OnboardingStep.RECEIVED
    identity: IdentityResult | None = None
    risk: RiskResult | None = None
    documentation: DocumentationResult | None = None
    policy_evidence: list[PolicyEvidence] = Field(default_factory=list)
    decision: Decision | None = None
    escalation: Escalation | None = None
    customer_response: str | None = None
    audit_log: list[AuditEvent] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
