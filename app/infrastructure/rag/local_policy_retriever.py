import re
from pathlib import Path

from app.application.ports.policy_retriever import PolicyRetrieverPort
from app.domain.models import PolicyEvidence


class LocalPolicyRetriever(PolicyRetrieverPort):
    """Small local retriever for phase 2. Replaceable by a vector DB through the same port."""

    def __init__(self, corpus_dir: str | Path):
        self.corpus_dir = Path(corpus_dir)
        self._sections = self._load_sections()

    def _load_sections(self) -> list[tuple[str, str, str]]:
        sections: list[tuple[str, str, str]] = []
        for path in sorted(self.corpus_dir.glob("*.md")):
            heading = "General"
            buffer: list[str] = []
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.startswith("## "):
                    if buffer:
                        sections.append((path.name, heading, "\n".join(buffer).strip()))
                    heading = line[3:].strip()
                    buffer = []
                elif line and not line.startswith("# "):
                    buffer.append(line)
            if buffer:
                sections.append((path.name, heading, "\n".join(buffer).strip()))
        return [section for section in sections if section[2]]

    @staticmethod
    def _tokens(text: str) -> set[str]:
        return {
            token
            for token in re.findall(r"[a-zA-ZáéíóúÁÉÍÓÚñÑ_]{3,}", text.casefold())
            if token not in {"para", "como", "debe", "esta", "este", "con", "los", "las"}
        }

    def retrieve(self, query: str, *, top_k: int = 3) -> list[PolicyEvidence]:
        query_tokens = self._tokens(query)
        ranked: list[PolicyEvidence] = []
        for source, section, content in self._sections:
            content_tokens = self._tokens(f"{section} {content}")
            overlap = len(query_tokens & content_tokens)
            denominator = max(len(query_tokens), 1)
            score = min(overlap / denominator, 1.0)
            if overlap:
                ranked.append(
                    PolicyEvidence(
                        source=source,
                        section=section,
                        content=content,
                        score=score,
                    )
                )
        ranked.sort(key=lambda item: item.score, reverse=True)
        return ranked[:top_k]
