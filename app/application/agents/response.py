import inspect

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from app.application.ports.llm import LLMPort
from app.domain.models import CustomerResponseOutput, Decision, OnboardingState
from app.infrastructure.security.pii_guard import PIIGuard, PIILeakError


class CustomerResponseAgent:
    """LLM-assisted wording only. Decision and workflow remain deterministic."""

    agent_id = "response_agent"

    def __init__(self, llm: LLMPort, pii_guard: PIIGuard):
        self.llm = llm
        self.pii_guard = pii_guard

    def run(self, state: OnboardingState) -> CustomerResponseOutput:
        safe_prompt = self._build_safe_prompt(state)
        forbidden = (state.request.prospect_name, state.request.document_id)
        self.pii_guard.assert_safe(safe_prompt, forbidden_values=forbidden)

        system_prompt = (
            "Eres un redactor de comunicaciones de onboarding bancario. "
            "No cambies DECISION, no inventes aprobaciones, no solicites PII y no agregues datos "
            "que no estén presentes en el contexto. Devuelve máximo dos frases en español."
        )
        try:
            generated = self._complete(system_prompt, safe_prompt).strip()
            self.pii_guard.assert_safe(generated, forbidden_values=forbidden)
            if not generated:
                raise ValueError("empty LLM response")
            text = self._localize(state.request.prospect_name, generated)
            return CustomerResponseOutput(text=text, used_llm=True)
        except Exception as exc:
            # Response wording is non-critical. Fail safe to a deterministic template.
            return CustomerResponseOutput(
                text=self._fallback(state),
                used_llm=False,
                fallback_reason=type(exc).__name__,
            )

    def _complete(self, system_prompt: str, user_prompt: str) -> str:
        if self._uses_port(self.llm):
            return self.llm.generate(system_prompt=system_prompt, user_prompt=user_prompt)
        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", "{system_prompt}"),
                ("human", "{user_prompt}"),
            ]
        )
        return (prompt | self.llm | StrOutputParser()).invoke(
            {"system_prompt": system_prompt, "user_prompt": user_prompt}
        )

    @staticmethod
    def _uses_port(llm: LLMPort) -> bool:
        generate = getattr(llm, "generate", None)
        if not callable(generate):
            return False
        try:
            parameters = inspect.signature(generate).parameters
        except (TypeError, ValueError):
            return False
        return "user_prompt" in parameters

    @staticmethod
    def _build_safe_prompt(state: OnboardingState) -> str:
        docs = ",".join(state.documentation.required_documents) if state.documentation else ""
        reason = state.escalation.reason_code if state.escalation else "none"
        policy_sections = ",".join(item.section for item in state.policy_evidence)
        return (
            f"DECISION={state.decision.value if state.decision else 'unknown'}\n"
            f"PRODUCT={state.request.product}\n"
            f"REQUIRED_DOCUMENTS={docs}\n"
            f"ESCALATION_REASON={reason}\n"
            f"POLICY_SECTIONS={policy_sections}"
        )

    @staticmethod
    def _localize(name: str, message: str) -> str:
        return f"{name}, {message[0].lower() + message[1:] if message else message}"

    @staticmethod
    def _fallback(state: OnboardingState) -> str:
        name = state.request.prospect_name
        if state.decision == Decision.APPROVED:
            docs = ", ".join(state.documentation.required_documents) if state.documentation else ""
            return f"{name}, la validación automática fue aprobada. Documentos requeridos: {docs}."
        if state.decision == Decision.REJECTED:
            return f"{name}, no fue posible aprobar automáticamente la solicitud con la información verificada."
        return (
            f"{name}, la solicitud requiere revisión adicional antes de continuar. "
            "No se tomará una decisión automática mientras exista incertidumbre."
        )
