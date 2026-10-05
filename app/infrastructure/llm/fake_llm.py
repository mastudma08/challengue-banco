from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult


class FakeLLM(BaseChatModel):
    """Offline LangChain chat model. Wording only; it never decides the case."""

    @property
    def _llm_type(self) -> str:
        return "fake-llm"

    def _generate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:
        text = "\n".join(_message_text(message) for message in messages)
        if "DECISION=approved" in text:
            content = (
                "La validación automática finalizó correctamente. "
                "Revisa los documentos indicados para continuar."
            )
        elif "DECISION=rejected" in text:
            content = (
                "La solicitud no pudo ser aprobada automáticamente "
                "con las verificaciones disponibles."
            )
        else:
            content = "La solicitud requiere una revisión humana adicional antes de continuar."
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=content))])


def _message_text(message) -> str:
    content = getattr(message, "content", "")
    if isinstance(content, str):
        return content
    return str(content)
