from cryptography.fernet import Fernet

from app.core.config import GITHUB_TOKEN_ENCRYPTION_KEY


def _get_fernet() -> Fernet:
    if not GITHUB_TOKEN_ENCRYPTION_KEY:
        raise RuntimeError(
            "GitHub token encryption key is not configured"
        )

    return Fernet(GITHUB_TOKEN_ENCRYPTION_KEY.encode())


def encrypt_github_token(token: str) -> str:
    return _get_fernet().encrypt(
        token.encode()
    ).decode()


def decrypt_github_token(encrypted_token: str) -> str:
    return _get_fernet().decrypt(
        encrypted_token.encode()
    ).decode()