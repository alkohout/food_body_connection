import os
from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import Text
from sqlalchemy.types import TypeDecorator

_fernet: Fernet | None = None


def get_fernet() -> Fernet:
    global _fernet
    if _fernet is None:
        key = os.environ.get("FIELD_ENCRYPTION_KEY")
        if not key:
            raise RuntimeError("FIELD_ENCRYPTION_KEY not set in environment")
        _fernet = Fernet(key.encode())
    return _fernet


class EncryptedString(TypeDecorator):
    """Transparent field-level encryption. Stores ciphertext in the DB column;
    returns plaintext to Python. Existing unencrypted values pass through safely."""

    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return get_fernet().encrypt(value.encode()).decode()

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        try:
            return get_fernet().decrypt(value.encode()).decode()
        except (InvalidToken, Exception):
            return value  # plaintext fallback for pre-migration rows
