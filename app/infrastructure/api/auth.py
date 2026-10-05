from collections.abc import Callable

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import Settings


security = HTTPBearer(auto_error=False)


def build_auth_dependency(settings: Settings, *, required_scopes: set[str]) -> Callable:
    def require_auth(
        credentials: HTTPAuthorizationCredentials | None = Depends(security),
    ) -> dict:
        if not settings.auth_enabled:
            return {"sub": "auth-disabled-local", "scope": "*"}
        if credentials is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing bearer token",
            )
        try:
            claims = jwt.decode(
                credentials.credentials,
                settings.jwt_secret,
                algorithms=[settings.jwt_algorithm],
                issuer=settings.jwt_issuer,
                audience=settings.jwt_audience,
            )
        except jwt.PyJWTError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid bearer token",
            ) from exc

        raw_scope = claims.get("scope", "")
        granted = set(raw_scope.split()) if isinstance(raw_scope, str) else set(raw_scope or [])
        if "*" not in granted and not required_scopes.issubset(granted):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient scope",
            )
        return claims

    return require_auth
