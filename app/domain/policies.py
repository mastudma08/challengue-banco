from dataclasses import dataclass

from app.domain.models import IdentityResult, RiskResult


@dataclass(frozen=True)
class BankOnboardingPolicy:
    identity_confidence_threshold: float = 0.8

    def identity_requires_review(self, result: IdentityResult) -> bool:
        return result.verified and result.confidence < self.identity_confidence_threshold

    @staticmethod
    def identity_is_rejected(result: IdentityResult) -> bool:
        return not result.verified

    @staticmethod
    def risk_requires_review(result: RiskResult) -> bool:
        return result.risk_level.lower() == "high"
