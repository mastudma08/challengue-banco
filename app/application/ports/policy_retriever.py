from abc import ABC, abstractmethod

from app.domain.models import PolicyEvidence


class PolicyRetrieverPort(ABC):
    @abstractmethod
    def retrieve(self, query: str, *, top_k: int = 3) -> list[PolicyEvidence]:
        raise NotImplementedError
