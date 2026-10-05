from app.application.ports.llm import LLMPort


class MockLLMProvider(LLMPort):
    """Local deterministic adapter. It proves the LLM boundary without requiring cloud credentials."""

    def generate(self, *, system_prompt: str, user_prompt: str) -> str:
        if "DECISION=approved" in user_prompt:
            return "La validación automática finalizó correctamente. Revisa los documentos indicados para continuar."
        if "DECISION=rejected" in user_prompt:
            return "La solicitud no pudo ser aprobada automáticamente con las verificaciones disponibles."
        return "La solicitud requiere una revisión humana adicional antes de continuar."
