"""Short-lived encrypted delivery payloads with one previous-key rotation slot."""

import json
from dataclasses import asdict
from hashlib import sha256

from cryptography.fernet import Fernet, MultiFernet

from app.invitations.config import InvitationSettings
from app.invitations.delivery import InvitationEmail


def delivery_cipher(settings: InvitationSettings) -> MultiFernet:
    """Encrypt with the current key; allow a previous key only while draining old work."""
    if settings.delivery_encryption_key is None:
        raise ValueError("invitation delivery encryption is not configured")
    keys = [settings.delivery_encryption_key]
    if settings.delivery_previous_encryption_key is not None:
        keys.append(settings.delivery_previous_encryption_key)
    return MultiFernet([Fernet(key.get_secret_value().encode()) for key in keys])


def _credential_fingerprint(settings: InvitationSettings) -> str:
    """Keep retries within one provider credential scope, even across configuration changes."""
    key = settings.delivery_api_key
    return sha256(
        key.get_secret_value().encode() if key is not None else b"unconfigured-test-adapter"
    ).hexdigest()


def encrypt_message(message: InvitationEmail, settings: InvitationSettings) -> str:
    """Keep the frozen provider payload confidential and authenticated at rest."""
    envelope = {
        "version": 1,
        "message": asdict(message),
        "credential_fingerprint": _credential_fingerprint(settings),
    }
    return delivery_cipher(settings).encrypt(json.dumps(envelope).encode()).decode()


def decrypt_message(ciphertext: str, settings: InvitationSettings) -> InvitationEmail:
    """Bound lifetime and reject retries after a provider credential/scope change."""
    payload = delivery_cipher(settings).decrypt(ciphertext.encode(), ttl=23 * 60 * 60)
    envelope = json.loads(payload)
    if envelope["version"] != 1 or envelope["credential_fingerprint"] != _credential_fingerprint(
        settings
    ):
        raise ValueError("provider credential scope changed")
    return InvitationEmail(**envelope["message"])
