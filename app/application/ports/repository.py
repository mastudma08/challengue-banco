from abc import ABC, abstractmethod

from app.domain.models import OnboardingState


class OnboardingRepository(ABC):
    @abstractmethod
    def save(self, state: OnboardingState) -> None:
        raise NotImplementedError

    @abstractmethod
    def get(self, onboarding_id: str) -> OnboardingState | None:
        raise NotImplementedError
