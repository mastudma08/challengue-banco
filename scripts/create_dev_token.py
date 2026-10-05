import os
from datetime import datetime, timedelta, timezone

import jwt


secret = os.getenv("JWT_SECRET", "change-me-in-real-environments")
algorithm = os.getenv("JWT_ALGORITHM", "HS256")
issuer = os.getenv("JWT_ISSUER", "onboarding-local")
audience = os.getenv("JWT_AUDIENCE", "onboarding-api")
now = datetime.now(timezone.utc)
payload = {
    "sub": "local-developer",
    "iss": issuer,
    "aud": audience,
    "scope": "onboarding:start onboarding:read",
    "iat": now,
    "exp": now + timedelta(hours=8),
}
print(jwt.encode(payload, secret, algorithm=algorithm))
