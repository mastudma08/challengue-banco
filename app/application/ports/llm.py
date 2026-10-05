from abc import ABC, abstractmethod


class LLMPort(ABC):
    @abstractmethod
    def generate(self, *, system_prompt: str, user_prompt: str) -> str:
        raise NotImplementedError
