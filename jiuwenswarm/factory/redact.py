"""Sanitize credential fields and embedded secrets without hiding engine metrics."""
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


def scrub_bytes(data):
    for pattern in SECRET_PATTERNS:
        data = pattern.sub(b'<redacted>', data)
    for key, value in os.environ.items():
        if value and sensitive(key, value):
            data = data.replace(value.encode(), b'<redacted>')
    return data


def sanitize(value):
    if isinstance(value, dict):
        return {scrub_bytes(str(k).encode()).decode(): '<redacted>' if sensitive(str(k), v)
                else sanitize(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [sanitize(v) for v in value]
    if isinstance(value, str):
        return scrub_bytes(value.encode()).decode()
    return value
