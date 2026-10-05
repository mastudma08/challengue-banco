from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from app.application.agents.documentation import DocumentationAgent
from app.application.agents.identity import IdentityAgent
from app.application.agents.response import CustomerResponseAgent
from app.application.agents.risk import RiskAgent
from app.application.ports.repository import OnboardingRepository
from app.domain.models import (
    AuditEvent,
    Decision,
    Escalation,
    IdentityResult,
    OnboardingState,
    OnboardingStatus,
    OnboardingStep,
    utc_now,
)
from app.domain.policies import BankOnboardingPolicy


class InvalidWorkflowTransition(RuntimeError):
    pass


class WorkflowState(TypedDict):
    onboarding_id: str
    route: str
    finish_event: str


class OnboardingStateGraph:
    """LangGraph engine. Banking decisions stay in code, not in the model."""

    _allowed_transitions: dict[OnboardingStep, set[OnboardingStep]] = {
        OnboardingStep.RECEIVED: {OnboardingStep.VERIFY_IDENTITY},
        OnboardingStep.VERIFY_IDENTITY: {
            OnboardingStep.CHECK_RISK,
            OnboardingStep.GENERATE_RESPONSE,
        },
        OnboardingStep.CHECK_RISK: {
            OnboardingStep.RETRIEVE_POLICY,
            OnboardingStep.GENERATE_RESPONSE,
        },
        OnboardingStep.RETRIEVE_POLICY: {
            OnboardingStep.PREPARE_DOCUMENTATION,
            OnboardingStep.GENERATE_RESPONSE,
        },
        OnboardingStep.PREPARE_DOCUMENTATION: {OnboardingStep.GENERATE_RESPONSE},
        OnboardingStep.GENERATE_RESPONSE: {OnboardingStep.COMPLETED},
        OnboardingStep.COMPLETED: set(),
    }

    def __init__(
        self,
        *,
        repository: OnboardingRepository,
        identity_agent: IdentityAgent,
        risk_agent: RiskAgent,
        documentation_agent: DocumentationAgent,
        response_agent: CustomerResponseAgent,
        policy: BankOnboardingPolicy,
    ):
        self.repository = repository
        self.identity_agent = identity_agent
        self.risk_agent = risk_agent
        self.documentation_agent = documentation_agent
        self.response_agent = response_agent
        self.policy = policy
        self.graph = self._compile()

    def invoke(self, state: OnboardingState) -> OnboardingState:
        state.status = OnboardingStatus.IN_PROGRESS
        self.repository.save(state)
        result = self.graph.invoke(
            {
                "onboarding_id": state.onboarding_id,
                "route": "CHECK_RISK",
                "finish_event": "",
            }
        )
        loaded = self.repository.get(result["onboarding_id"])
        if loaded is None:
            raise RuntimeError("onboarding state disappeared during workflow")
        return loaded

    @staticmethod
    def identity_route(identity: IdentityResult, policy: BankOnboardingPolicy) -> str:
        if identity.confidence < policy.identity_confidence_threshold:
            return "MANUAL_REVIEW"
        if policy.identity_is_rejected(identity):
            return "REJECTED"
        return "CHECK_RISK"

    def _compile(self):
        graph = StateGraph(WorkflowState)
        graph.add_node("identity", self._identity_node)
        graph.add_node("risk", self._risk_node)
        graph.add_node("retrieval", self._retrieval_node)
        graph.add_node("policy", self._policy_node)
        graph.add_node("documentation", self._documentation_node)
        graph.add_node("response", self._response_node)
        graph.add_edge(START, "identity")
        graph.add_conditional_edges(
            "identity",
            self._route,
            {
                "REJECTED": "response",
                "MANUAL_REVIEW": "response",
                "CHECK_RISK": "risk",
            },
        )
        graph.add_conditional_edges(
            "risk",
            self._route,
            {
                "MANUAL_REVIEW": "response",
                "RETRIEVE_POLICY": "retrieval",
            },
        )
        graph.add_conditional_edges(
            "retrieval",
            self._route,
            {
                "MANUAL_REVIEW": "response",
                "POLICY": "policy",
            },
        )
        graph.add_conditional_edges(
            "policy",
            self._route,
            {
                "MANUAL_REVIEW": "response",
                "PREPARE_DOCUMENTATION": "documentation",
            },
        )
        graph.add_conditional_edges(
            "documentation",
            self._route,
            {
                "APPROVED": "response",
                "MANUAL_REVIEW": "response",
            },
        )
        graph.add_edge("response", END)
        return graph.compile()

    @staticmethod
    def _route(graph_state: WorkflowState) -> str:
        return graph_state["route"]

    def _identity_node(self, graph_state: WorkflowState) -> WorkflowState:
        state = self._load(graph_state["onboarding_id"])
        try:
            self._transition(state, OnboardingStep.VERIFY_IDENTITY)
            state.identity = self.identity_agent.run(state.request)
            self._record(
                state,
                "identity_checked",
                {"verified": state.identity.verified, "confidence": state.identity.confidence},
            )
        except Exception as exc:
            self._mark_manual_review(
                state,
                reason_code="IDENTITY_TOOL_FAILURE",
                message="No se pudo completar la verificación de identidad.",
                recommended_action="Reintentar y, si persiste, derivar a validación KYC manual.",
                error=exc,
            )
            return self._update(state, "MANUAL_REVIEW", "escalated")

        route = self.identity_route(state.identity, self.policy)
        if route == "MANUAL_REVIEW":
            self._mark_manual_review(
                state,
                reason_code="IDENTITY_LOW_CONFIDENCE",
                message=(
                    f"Confianza {state.identity.confidence:.2f} inferior al umbral "
                    f"{self.policy.identity_confidence_threshold:.2f}."
                ),
                recommended_action="Solicitar evidencia adicional o validación manual de identidad.",
            )
            return self._update(state, "MANUAL_REVIEW", "escalated")
        if route == "REJECTED":
            return self._update(state, "REJECTED", "identity_not_verified")
        return self._update(state, "CHECK_RISK", "")

    def _risk_node(self, graph_state: WorkflowState) -> WorkflowState:
        state = self._load(graph_state["onboarding_id"])
        try:
            self._transition(state, OnboardingStep.CHECK_RISK)
            state.risk = self.risk_agent.run(state.request)
            self._record(
                state,
                "risk_checked",
                {"risk_level": state.risk.risk_level, "matches": state.risk.matches},
            )
        except Exception as exc:
            self._mark_manual_review(
                state,
                reason_code="RISK_TOOL_FAILURE",
                message="No se pudo completar la consulta de listas de riesgo.",
                recommended_action="Reintentar y bloquear la decisión automática hasta obtener resultado.",
                error=exc,
            )
            return self._update(state, "MANUAL_REVIEW", "escalated")

        if self.policy.risk_requires_review(state.risk):
            self._mark_manual_review(
                state,
                reason_code="HIGH_RISK_MATCH",
                message="La verificación devolvió nivel de riesgo high.",
                recommended_action="Escalar el caso a Cumplimiento/AML para decisión humana.",
            )
            return self._update(state, "MANUAL_REVIEW", "escalated")
        return self._update(state, "RETRIEVE_POLICY", "")

    def _retrieval_node(self, graph_state: WorkflowState) -> WorkflowState:
        state = self._load(graph_state["onboarding_id"])
        try:
            self._transition(state, OnboardingStep.RETRIEVE_POLICY)
            evidence = self.documentation_agent.retrieve_policy(state.request)
            if not evidence:
                raise LookupError("no policy evidence found")
            state.policy_evidence = evidence
            self._record(
                state,
                "policy_retrieved",
                {"sources": [item.source for item in state.policy_evidence]},
            )
        except Exception as exc:
            self._mark_manual_review(
                state,
                reason_code="POLICY_RETRIEVAL_FAILURE",
                message="No fue posible recuperar evidencia de política para el producto.",
                recommended_action="Validar la política vigente antes de preparar documentación.",
                error=exc,
            )
            return self._update(state, "MANUAL_REVIEW", "escalated")
        return self._update(state, "POLICY", "")

    def _policy_node(self, graph_state: WorkflowState) -> WorkflowState:
        state = self._load(graph_state["onboarding_id"])
        if not state.policy_evidence:
            self._mark_manual_review(
                state,
                reason_code="POLICY_RETRIEVAL_FAILURE",
                message="No fue posible recuperar evidencia de política para el producto.",
                recommended_action="Validar la política vigente antes de preparar documentación.",
                error=LookupError("no policy evidence found"),
            )
            return self._update(state, "MANUAL_REVIEW", "escalated")
        return self._update(state, "PREPARE_DOCUMENTATION", "")

    def _documentation_node(self, graph_state: WorkflowState) -> WorkflowState:
        state = self._load(graph_state["onboarding_id"])
        try:
            self._transition(state, OnboardingStep.PREPARE_DOCUMENTATION)
            output = self.documentation_agent.prepare(state.request, state.policy_evidence)
            state.documentation = output.documentation
            self._record(
                state,
                "documentation_prepared",
                {"required_documents": state.documentation.required_documents},
            )
        except Exception as exc:
            self._mark_manual_review(
                state,
                reason_code="DOCUMENTATION_TOOL_FAILURE",
                message="No se pudo preparar la documentación requerida.",
                recommended_action="Reintentar la preparación documental o derivar a operación manual.",
                error=exc,
            )
            return self._update(state, "MANUAL_REVIEW", "escalated")
        return self._update(state, "APPROVED", "policy_approved")

    def _response_node(self, graph_state: WorkflowState) -> WorkflowState:
        state = self._load(graph_state["onboarding_id"])
        decision = {
            "APPROVED": Decision.APPROVED,
            "REJECTED": Decision.REJECTED,
            "MANUAL_REVIEW": Decision.MANUAL_REVIEW,
        }[graph_state["route"]]
        state.decision = decision
        state.status = {
            Decision.APPROVED: OnboardingStatus.APPROVED,
            Decision.REJECTED: OnboardingStatus.REJECTED,
            Decision.MANUAL_REVIEW: OnboardingStatus.MANUAL_REVIEW,
        }[decision]
        self._transition(state, OnboardingStep.GENERATE_RESPONSE)
        response = self.response_agent.run(state)
        state.customer_response = response.text
        self._record(
            state,
            "customer_response_generated",
            {"used_llm": response.used_llm, "fallback_reason": response.fallback_reason},
        )
        self._transition(state, OnboardingStep.COMPLETED)
        self._record(state, graph_state["finish_event"], {"decision": decision.value})
        return self._update(state, graph_state["route"], graph_state["finish_event"])

    def _load(self, onboarding_id: str) -> OnboardingState:
        state = self.repository.get(onboarding_id)
        if state is None:
            raise RuntimeError("onboarding state disappeared during workflow")
        return state

    @staticmethod
    def _update(state: OnboardingState, route: str, finish_event: str) -> WorkflowState:
        return {
            "onboarding_id": state.onboarding_id,
            "route": route,
            "finish_event": finish_event,
        }

    def _mark_manual_review(
        self,
        state: OnboardingState,
        *,
        reason_code: str,
        message: str,
        recommended_action: str,
        error: Exception | None = None,
    ) -> None:
        state.escalation = Escalation(
            reason_code=reason_code,
            stage=state.current_step,
            message=message,
            recommended_action=recommended_action,
        )
        details = {"reason_code": reason_code}
        if error is not None:
            details["error_type"] = type(error).__name__
        self._record(state, "manual_review_required", details)

    def _transition(self, state: OnboardingState, target: OnboardingStep) -> None:
        allowed = self._allowed_transitions[state.current_step]
        if target not in allowed:
            raise InvalidWorkflowTransition(
                f"transition {state.current_step.value} -> {target.value} is not allowed"
            )
        previous = state.current_step
        state.current_step = target
        state.updated_at = utc_now()
        state.audit_log.append(
            AuditEvent(
                step=target,
                event="workflow_transition",
                details={"from": previous.value, "to": target.value},
            )
        )
        self.repository.save(state)

    def _record(self, state: OnboardingState, event: str, details: dict | None = None) -> None:
        state.audit_log.append(
            AuditEvent(step=state.current_step, event=event, details=details or {})
        )
        state.updated_at = utc_now()
        self.repository.save(state)
