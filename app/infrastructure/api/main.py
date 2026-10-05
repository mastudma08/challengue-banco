from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse

from app.application.agents.documentation import DocumentationAgent
from app.application.agents.identity import IdentityAgent
from app.application.agents.response import CustomerResponseAgent
from app.application.agents.risk import RiskAgent
from app.application.orchestrator import OnboardingOrchestrator
from app.application.workflows.onboarding_graph import OnboardingStateGraph
from app.config import Settings, get_settings
from app.domain.models import OnboardingRequest, OnboardingState
from app.domain.policies import BankOnboardingPolicy
from app.infrastructure.api.auth import build_auth_dependency
from app.infrastructure.api.schemas import OnboardingPublicResponse, StartOnboardingRequest
from app.infrastructure.llm.fake_llm import FakeLLM
from app.infrastructure.llm.openai_compatible_provider import OpenAICompatibleLLMProvider
from app.infrastructure.persistence.sqlite_repository import SQLiteOnboardingRepository
from app.infrastructure.rag.local_policy_retriever import LocalPolicyRetriever
from app.infrastructure.security.pii_guard import PIIGuard
from app.infrastructure.tools.gateway import ToolGateway
from app.infrastructure.tools.mocks import MockExternalTools


def _build_llm(settings: Settings):
    if settings.llm_mode in {"mock", "fake"}:
        return FakeLLM()
    return OpenAICompatibleLLMProvider(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        model=settings.llm_model,
        timeout_seconds=settings.llm_timeout_seconds,
    )


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    repository = SQLiteOnboardingRepository(settings.database_url)
    gateway = ToolGateway(MockExternalTools())
    retriever = LocalPolicyRetriever(Path(settings.policy_corpus_path))
    response_agent = CustomerResponseAgent(_build_llm(settings), PIIGuard())
    workflow = OnboardingStateGraph(
        repository=repository,
        identity_agent=IdentityAgent(gateway),
        risk_agent=RiskAgent(gateway),
        documentation_agent=DocumentationAgent(gateway, retriever),
        response_agent=response_agent,
        policy=BankOnboardingPolicy(settings.identity_confidence_threshold),
    )
    orchestrator = OnboardingOrchestrator(repository, workflow)

    require_start = build_auth_dependency(settings, required_scopes={"onboarding:start"})
    require_read = build_auth_dependency(settings, required_scopes={"onboarding:read"})

    app = FastAPI(
        title=settings.app_name,
        version="2.0.0-phase2",
        description=(
            "Secure API boundary + LangGraph workflow + specialized agents + "
            "policy retrieval + PII-safe FakeLLM wording."
        ),
    )
    app.state.repository = repository
    app.state.orchestrator = orchestrator
    app.state.workflow = workflow

    @app.middleware("http")
    async def api_security_boundary(request: Request, call_next):
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > settings.max_request_bytes:
            return JSONResponse(status_code=413, content={"detail": "Request body too large"})
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.get("/health")
    def health() -> dict[str, str]:
        return {
            "status": "ok",
            "environment": settings.environment,
            "workflow": "langgraph",
            "llm_mode": settings.llm_mode,
        }

    @app.post(
        "/api/v1/onboarding/start",
        response_model=OnboardingPublicResponse,
        status_code=status.HTTP_200_OK,
        dependencies=[Depends(require_start)],
    )
    def start_onboarding(request: StartOnboardingRequest) -> OnboardingPublicResponse:
        state = orchestrator.start(OnboardingRequest.model_validate(request.model_dump()))
        return OnboardingPublicResponse.model_validate(state)

    @app.get(
        "/api/v1/onboarding/{onboarding_id}",
        response_model=OnboardingPublicResponse,
        dependencies=[Depends(require_read)],
    )
    def get_onboarding(onboarding_id: str) -> OnboardingPublicResponse:
        state = orchestrator.get(onboarding_id)
        if state is None:
            raise HTTPException(status_code=404, detail="Onboarding not found")
        return OnboardingPublicResponse.model_validate(state)

    return app


app = create_app()
