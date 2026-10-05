import unicodedata

from app.application.ports.policy_retriever import PolicyRetrieverPort
from app.application.ports.tool_gateway import ToolGatewayPort
from app.domain.models import (
    DocumentationAgentOutput,
    DocumentationResult,
    OnboardingRequest,
    PolicyEvidence,
)


class PolicyEvidenceMismatch(RuntimeError):
    pass


class DocumentationAgent:
    agent_id = "documentation_agent"

    _policy_labels = {
        "cedula_identidad": "cedula de identidad",
        "formulario_kyc": "formulario kyc",
        "aceptacion_terminos": "aceptacion de terminos",
        "declaracion_origen_fondos": "declaracion de origen de fondos",
    }

    def __init__(self, gateway: ToolGatewayPort, policy_retriever: PolicyRetrieverPort):
        self.gateway = gateway
        self.policy_retriever = policy_retriever

    def retrieve_policy(self, request: OnboardingRequest) -> list[PolicyEvidence]:
        query = (
            f"onboarding documentos KYC producto {request.product} "
            "riesgo identidad incertidumbre"
        )
        return self.policy_retriever.retrieve(query, top_k=3)

    def prepare(
        self,
        request: OnboardingRequest,
        policy_evidence: list[PolicyEvidence],
    ) -> DocumentationAgentOutput:
        raw = self.gateway.execute(
            self.agent_id,
            "prepare_documentation",
            product=request.product,
            client_data={
                "prospect_name": request.prospect_name,
                "document_id": request.document_id,
            },
        )
        documentation = DocumentationResult.model_validate(raw)
        self._assert_supported_by_policy(documentation, policy_evidence)
        return DocumentationAgentOutput(
            documentation=documentation,
            policy_evidence=policy_evidence,
        )

    def _assert_supported_by_policy(
        self,
        documentation: DocumentationResult,
        policy_evidence: list[PolicyEvidence],
    ) -> None:
        corpus = self._normalize(" ".join(item.content for item in policy_evidence))
        unsupported = []
        for document in documentation.required_documents:
            label = self._policy_labels.get(document, document.replace("_", " "))
            if self._normalize(label) not in corpus:
                unsupported.append(document)
        if unsupported:
            raise PolicyEvidenceMismatch(
                f"documentation not supported by retrieved policy evidence: {unsupported}"
            )

    @staticmethod
    def _normalize(value: str) -> str:
        decomposed = unicodedata.normalize("NFKD", value.casefold())
        return " ".join("".join(ch for ch in decomposed if not unicodedata.combining(ch)).split())
