"""
Creates ServiceApiKey rows. The raw key is generated here, hashed before
storage, and returned to the caller exactly once — nothing else in the
codebase ever sees or stores the plaintext again.

Kept in its own module (not in views) so the management command and the
Django admin share one implementation and can't drift apart.
"""
import hashlib
import secrets

from ..models import ServiceApiKey


def generate_service_api_key(name, user=None):
    """
    Returns (raw_key, ServiceApiKey).

    raw_key is shown to the operator exactly once and is unrecoverable
    afterwards — only its SHA-256 hash is persisted. A 40-byte urlsafe
    token gives far more entropy than the key space needs, and the
    'aepfm_' prefix makes leaked keys recognisable in logs and audits.
    """
    raw = 'aepfm_' + secrets.token_urlsafe(40)
    hashed = hashlib.sha256(raw.encode()).hexdigest()
    key = ServiceApiKey.objects.create(name=name, hashedKey=hashed, createdBy=user)
    return raw, key
