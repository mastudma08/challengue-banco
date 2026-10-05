from app.application.ports.repository import OnboardingRepository
from app.application.workflows.onboarding_graph import OnboardingStateGraph
from app.domain.models import AuditEvent, OnboardingRequest, OnboardingState, OnboardingStep


class OnboardingOrchestrator:
    """Application façade. FastAPI enters here; LangGraph owns sequencing."""

    def __init__(self, repository: OnboardingRepository, workflow: OnboardingStateGraph):
        self.repository = repository
        self.workflow = workflow

    def start(self, request: OnboardingRequest) -> OnboardingState:
        state = OnboardingState(request=request)
        state.audit_log.append(
            AuditEvent(step=OnboardingStep.RECEIVED, event="request_received")
        )
        self.repository.save(state)
        return self.workflow.invoke(state)

    def get(self, onboarding_id: str) -> OnboardingState | None:
        return self.repository.get(onboarding_id)
