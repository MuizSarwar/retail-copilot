"""Security layer — password hashing and JWT utilities.

Argon2id password hashing and JWT create/verify are implemented here.
"""

from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError


# Argon2id hasher with recommended parameters for a beginner project.
# time_cost=3, memory_cost=65536 (64 MiB), parallelism=4 are
# the Argon2 library defaults and provide good security.
ph = PasswordHasher()


def hash_password(password: str) -> str:
    """Hash a plain-text password using Argon2id.

    Returns the encoded hash string that can be stored in the
    database.  The hash includes a random salt and all parameters,
    so it is safe to store directly.
    """
    return ph.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain-text password against an Argon2id hash.

    Returns True if the password matches, False otherwise.
    """
    try:
        ph.verify(hashed_password, plain_password)
        return True
    except VerifyMismatchError:
        return False


def create_access_token(
    user_id: int,
    secret_key: str,
    algorithm: str,
    expire_minutes: int,
) -> str:
    """Create a JWT access token.

    Claims:
    - sub: user ID (subject) as a string
    - exp: expiration timestamp (UTC)
    - iat: issued at timestamp (UTC)

    The token contains only the user ID and expiry — never the role,
    password, or other sensitive data.  The role is loaded from the
    database on each authenticated request.
    """
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=expire_minutes)

    payload = {
        "sub": str(user_id),
        "exp": expire,
        "iat": now,
    }

    return jwt.encode(payload, secret_key, algorithm=algorithm)


def verify_access_token(
    token: str,
    secret_key: str,
    algorithm: str,
) -> dict:
    """Verify a JWT access token and return its payload.

    Raises jwt.ExpiredSignatureError if the token has expired.
    Raises jwt.InvalidTokenError if the token is invalid.
    """
    return jwt.decode(token, secret_key, algorithms=[algorithm])
