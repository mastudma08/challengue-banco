from app.application.agents.response import CustomerResponseAgent
from app.application.ports.llm import LLMPort
from app.domain.models import Decision, OnboardingRequest, OnboardingState
from app.infrastructure.security.pii_guard import PIIGuard


class RecordingLLM(LLMPort):
    def __init__(self):
        self.user_prompt = ""

    def generate(self, *, system_prompt: str, user_prompt: str) -> str:
        self.user_prompt = user_prompt
        return "La solicitud requiere una revisión humana adicional antes de continuar."


def test_raw_pii_is_not_sent_to_llm():
    llm = RecordingLLM()
    agent = CustomerResponseAgent(llm, PIIGuard())
    state = OnboardingState(
        request=OnboardingRequest(
            prospect_name="Juan Perez",
            document_id="1712345678",
            product="cuenta_ahorros",
        ),
        decision=Decision.MANUAL_REVIEW,
    )
    output = agent.run(state)
    assert output.used_llm is True
    assert "Juan Perez" not in llm.user_prompt
    assert "1712345678" not in llm.user_prompt
    assert output.text.startswith("Juan Perez,")
