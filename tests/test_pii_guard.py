import pytest

from app.infrastructure.security.pii_guard import PIIGuard, PIILeakError


def test_pii_guard_blocks_document_id():
    with pytest.raises(PIILeakError):
        PIIGuard().assert_safe("document=1712345678")


def test_pii_guard_blocks_explicit_forbidden_name():
    with pytest.raises(PIILeakError):
        PIIGuard().assert_safe("cliente=Juan Perez", forbidden_values=("Juan Perez",))
