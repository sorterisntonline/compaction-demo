#!/usr/bin/env python3
"""
Signed Snippets.
"""

import hmac
import hashlib
import uuid
import time
import base64
import re

SECRET = hashlib.sha256(f"snippets-{uuid.uuid4()}".encode()).digest()
_nonces: dict[str, float] = {}
NONCE_TTL = 3600


def _clean_expired():
    now = time.time()
    for n in [n for n, exp in _nonces.items() if exp < now]:
        del _nonces[n]


def generate_nonce() -> str:
    _clean_expired()
    nonce = uuid.uuid4().hex
    _nonces[nonce] = time.time() + NONCE_TTL
    return nonce


def consume_nonce(nonce: str) -> bool:
    _clean_expired()
    if nonce in _nonces:
        del _nonces[nonce]
        return True
    return False


def sign(code: str, nonce: str) -> str:
    msg = f"{code}|{nonce}".encode()
    return base64.urlsafe_b64encode(hmac.new(SECRET, msg, hashlib.sha256).digest()).decode()


def verify(code: str, nonce: str, sig: str) -> bool:
    return hmac.compare_digest(sign(code, nonce), sig)


def scrub(value: str) -> str:
    return value.replace("\\", "\\\\").replace("'", "\\'").replace('"', '\\"')


def snippet_hidden(code: str) -> list:
    """Hidden inputs for a signed snippet."""
    nonce = generate_nonce()
    sig = sign(code, nonce)
    return [
        ["input", {"type": "hidden", "name": "__snippet__", "value": code}],
        ["input", {"type": "hidden", "name": "__sig__", "value": sig}],
        ["input", {"type": "hidden", "name": "__nonce__", "value": nonce}],
    ]


def eval_snippet(code: str, form_data: dict, context: dict):
    """Substitute $vars and eval. Returns result or raises."""
    for key, value in form_data.items():
        code = code.replace(f'${key}', f"'{scrub(value)}'")
    
    remaining = re.findall(r'\$\w+', code)
    if remaining:
        raise ValueError(f"Missing: {remaining}")
    
    return eval(code, context)
