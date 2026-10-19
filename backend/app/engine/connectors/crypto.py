"""FairCart AI — Cryptographic Credential Vault (Slice 5)

Provides vetted Fernet authenticated encryption (AES-128-CBC with HMAC-SHA256)
for external connector API keys, service accounts, and OAuth refresh tokens.

Security Invariants:
1. Production connector credentials must NEVER be encrypted with a predictable fallback key.
2. If a valid key is missing or insecure, credential persistence and activation are refused.
3. Credentials, decrypted tokens, and raw keys are never logged.
4. Non-connector platform features remain fully functional when vault keys are unconfigured.
"""

import base64
import hashlib
import json
import logging
import os
from typing import Any

from cryptography.fernet import Fernet

from backend.app.config import settings

logger = logging.getLogger("faircart.twin.connectors.crypto")

PROHIBITED_INSECURE_KEYS = {
    "faircart-decision-twin-internal-vault-secret-key-2026",
    "default",
    "changeme",
    "secret",
    "secretkey",
    "password",
    "admin",
    "test",
    "12345678",
}


class VaultKeyError(ValueError):
    """Base exception for connector credential vault key failures."""
    pass


class MissingVaultKeyError(VaultKeyError):
    """Raised when no vault encryption key is configured."""
    pass


class InvalidVaultKeyError(VaultKeyError):
    """Raised when a configured vault key is insecure, trivial, or too short."""
    pass


def get_vault_encryption_key(key_override: str | bytes | None = None) -> bytes:
    """Derives a vetted 32-byte Fernet key from the environment key or an explicit override.

    Fernet primitive:
      AES-128 in CBC mode with HMAC-SHA256 authenticated encryption.
      The derived 32-byte secret is partitioned into a 16-byte HMAC signing key
      and a 16-byte AES encryption key.

    Resolution order:
      1. Explicit key_override (used in isolated unit tests).
      2. settings.CONNECTOR_VAULT_KEY / os.environ["CONNECTOR_VAULT_KEY"]
      3. settings.SECRET_KEY / os.environ["SECRET_KEY"]

    Raises:
      MissingVaultKeyError: if no key is found.
      InvalidVaultKeyError: if the key is trivial or under 16 characters.
    """
    raw_key: str | bytes | None = key_override
    if raw_key is None:
        raw_key = getattr(settings, "CONNECTOR_VAULT_KEY", None) or os.environ.get("CONNECTOR_VAULT_KEY")
    if raw_key is None:
        raw_key = getattr(settings, "SECRET_KEY", None) or os.environ.get("SECRET_KEY")

    if not raw_key:
        raise MissingVaultKeyError(
            "Connector vault encryption key is missing. Set CONNECTOR_VAULT_KEY or SECRET_KEY in environment. "
            "Publicly predictable fallback keys are strictly prohibited in production."
        )

    if isinstance(raw_key, bytes):
        raw_str = raw_key.decode("utf-8", errors="replace").strip()
    else:
        raw_str = str(raw_key).strip()

    if raw_str.lower() in PROHIBITED_INSECURE_KEYS or len(raw_str) < 16:
        raise InvalidVaultKeyError(
            "Configured vault encryption key is prohibited or too short (minimum 16 characters required)."
        )

    digest = hashlib.sha256(raw_str.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


def encrypt_credentials(credentials: dict[str, Any], key_override: str | bytes | None = None) -> str:
    """Encrypts credentials dictionary to an authenticated ciphertext string."""
    key = get_vault_encryption_key(key_override)
    f = Fernet(key)
    raw_json = json.dumps(credentials).encode("utf-8")
    token = f.encrypt(raw_json)
    return token.decode("utf-8")


def decrypt_credentials(encrypted_token: str, key_override: str | bytes | None = None) -> dict[str, Any]:
    """Decrypts ciphertext string back into credentials dictionary.

    Returns empty dict on decryption failure or missing key. Never logs secrets.
    """
    if not encrypted_token or not encrypted_token.strip():
        return {}
    try:
        key = get_vault_encryption_key(key_override)
        f = Fernet(key)
        decrypted_bytes = f.decrypt(encrypted_token.strip().encode("utf-8"))
        return json.loads(decrypted_bytes.decode("utf-8"))
    except MissingVaultKeyError:
        logger.error("Decryption refused: connector vault key is not configured.")
        return {}
    except InvalidVaultKeyError:
        logger.error("Decryption refused: connector vault key is invalid.")
        return {}
    except Exception:
        logger.error("Decryption failure: authentication tag or token invalid.")
        return {}


def mask_credential_value(val: str) -> str:
    """Masks secret strings for audit logs and API responses (e.g. 'shpat_...1a2b')."""
    if not val:
        return ""
    clean = str(val).strip()
    if len(clean) <= 6:
        return "***"
    return f"{clean[:4]}...{clean[-4:]}"
