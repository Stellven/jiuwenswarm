"""Sanitize credential fields and embedded secrets without hiding engine metrics."""
from functools import lru_cache
import os
import re

SECRET_PATTERNS = [
    re.compile(rb'eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}'),
    re.compile(rb'(?i)bearer\s+[A-Za-z0-9._-]{16,}'),
    re.compile(rb'(?<![A-Za-z0-9])sk-[A-Za-z0-9_-]{20,}'),
    re.compile(rb'(?<![\w.+-])[A-Za-z0-9_+.-]+@(?:[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?\.)+[A-Za-z]{2,}(?![\w.-])'),
    re.compile(rb'''(?ix)(?:access_token|refresh_token|id_token|api_key|password|secret|token)["']?\s*[:=]\s*["']?[A-Za-z0-9_./+-]{16,}'''),
    re.compile(rb'(?i)(?:state|code|code_challenge)=[A-Za-z0-9_%-]{12,}'),
]
CREDENTIAL_KEY = re.compile(r'(?i)(?:^|_)(access_token|refresh_token|id_token|api_key|authorization|password|secret|auth_json|private_key|credential)$')


def sensitive(key, value):
    return bool(CREDENTIAL_KEY.search(key) or
                (key.lower().endswith('_token') and isinstance(value, str)
                 and re.fullmatch(r'[A-Za-z0-9_./+\-=]{20,}', value)))


def _environment_secrets():
    return tuple(value.encode() for key, value in os.environ.items() if value and sensitive(key, value))


def _scrub_bytes(data, secrets):
    for pattern in SECRET_PATTERNS:
        data = pattern.sub(b'<redacted>', data)
    for secret in secrets:
        data = data.replace(secret, b'<redacted>')
    return data


def scrub_bytes(data):
    return _scrub_bytes(data, _environment_secrets())


def sanitize(value):
    secrets = _environment_secrets()

    @lru_cache(maxsize=4096)
    def short_text(text):
        return _scrub_bytes(text.encode(), secrets).decode()

    def clean(item):
        if isinstance(item, dict):
            return {short_text(str(k)): '<redacted>' if sensitive(str(k), v)
                    else clean(v) for k, v in item.items()}
        if isinstance(item, (list, tuple)):
            return [clean(v) for v in item]
        if isinstance(item, str):
            return (short_text(item) if len(item) <= 1024 else
                    _scrub_bytes(item.encode(), secrets).decode())
        return item

    return clean(value)
