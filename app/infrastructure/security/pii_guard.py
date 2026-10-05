import re


class PIILeakError(ValueError):
    pass


class PIIGuard:
    """Deterministic guard used before any prompt leaves the application boundary."""

    _document_pattern = re.compile(r"(?<!\d)\d{10}(?!\d)")

    def assert_safe(self, text: str, *, forbidden_values: tuple[str, ...] = ()) -> None:
        lowered = text.casefold()
        for value in forbidden_values:
            candidate = value.strip()
            if candidate and candidate.casefold() in lowered:
                raise PIILeakError("prompt contains a forbidden raw PII value")
        if self._document_pattern.search(text):
            raise PIILeakError("prompt contains a possible 10-digit document identifier")
