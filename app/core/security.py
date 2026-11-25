"""Security layer — password hashing and JWT utilities.

Argon2id password hashing is implemented here.  JWT create/verify
will be added in Parts 7-8 (Authentication and Authorization).
"""

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
