import json
from urllib import request

from app.application.ports.llm import LLMPort


class OpenAICompatibleLLMProvider(LLMPort):
    """Optional adapter for an OpenAI-compatible /v1/chat/completions endpoint."""

    def __init__(self, *, base_url: str, api_key: str, model: str, timeout_seconds: float = 15.0):
        self.url = f"{base_url.rstrip('/')}/v1/chat/completions"
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds

    def generate(self, *, system_prompt: str, user_prompt: str) -> str:
        payload = json.dumps(
            {
                "model": self.model,
                "temperature": 0,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            }
        ).encode("utf-8")
        req = request.Request(
            self.url,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )
        with request.urlopen(req, timeout=self.timeout_seconds) as response:
            body = json.loads(response.read().decode("utf-8"))
        return body["choices"][0]["message"]["content"].strip()
