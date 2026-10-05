from pathlib import Path

import pytest

from app.application.agents.documentation import DocumentationAgent
from app.application.agents.identity import IdentityAgent
from app.application.agents.response import CustomerResponseAgent
from app.application.agents.risk import RiskAgent
from app.application.workflows.onboarding_workflow import InvalidWorkflowTransition, OnboardingWorkflow
from app.domain.models import IdentityResult, OnboardingRequest, OnboardingState, OnboardingStep
from app.domain.policies import BankOnboardingPolicy
from app.infrastructure.llm.mock_provider import MockLLMProvider
from app.infrastructure.persistence.sqlite_repository import SQLiteOnboardingRepository
from app.infrastructure.rag.local_policy_retriever import LocalPolicyRetriever
from app.infrastructure.security.pii_guard import PIIGuard
from app.infrastructure.tools.gateway import ToolGateway
from app.infrastructure.tools.mocks import MockExternalTools


def test_workflow_cannot_jump_directly_to_documentation(tmp_path: Path):
    repo = SQLiteOnboardingRepository(f"sqlite:///{tmp_path / 'workflow.db'}")
    gateway = ToolGateway(MockExternalTools())
    workflow = OnboardingWorkflow(
        repository=repo,
        identity_agent=IdentityAgent(gateway),
        risk_agent=RiskAgent(gateway),
        documentation_agent=DocumentationAgent(
            gateway,
            LocalPolicyRetriever(Path(__file__).resolve().parents[1] / "docs" / "policies"),
        ),
        response_agent=CustomerResponseAgent(MockLLMProvider(), PIIGuard()),
        policy=BankOnboardingPolicy(),
    )
    state = OnboardingState(
        request=OnboardingRequest(
            prospect_name="Juan Perez",
            document_id="1712345678",
            product="cuenta_ahorros",
        )
    )
    with pytest.raises(InvalidWorkflowTransition):
        workflow._transition(state, OnboardingStep.PREPARE_DOCUMENTATION)


def test_low_confidence_has_priority_over_rejection():
    route = OnboardingWorkflow.identity_route(
        IdentityResult(verified=False, confidence=0.5),
        BankOnboardingPolicy(0.8),
    )
    assert route == "MANUAL_REVIEW"
