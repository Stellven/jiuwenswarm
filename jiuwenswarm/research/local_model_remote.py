"""Fixed, diskless SSH helper. Importing this module performs no I/O."""
import json
import math
import socket
import sys
import urllib.error
import urllib.parse
import urllib.request

MAX_RESPONSE_BYTES = 1024 * 1024


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def execute(payload):
    """Execute exactly one loopback request; never retry or reflect error bodies."""
    unknown = dict(outcome='outcome_unknown', http_status=None,
                   response_text=None, provider_request_id=None)
    if set(payload) != {'base_url', 'model', 'prompt', 'timeout_s'}:
        raise ValueError('invalid_request')
    url = urllib.parse.urlsplit(payload['base_url'])
    if (url.scheme != 'http' or url.hostname not in {'127.0.0.1', '::1'}
            or url.username or url.password or url.path != '/v1' or url.query or url.fragment):
        raise ValueError('invalid_request')
    model = payload['model']
    if (not isinstance(payload['prompt'], str) or type(payload['timeout_s']) not in {int, float}
            or not math.isfinite(payload['timeout_s']) or not 0 < payload['timeout_s'] <= 600):
        raise ValueError('invalid_request')
    body = {'model': model['model_name'], 'messages': [{'role': 'user', 'content': payload['prompt']}],
            'stream': False, 'max_tokens': model['max_output_tokens'],
            'temperature': model['temperature'],
            'chat_template_kwargs': {'enable_thinking': model['enable_thinking']}}
    request = urllib.request.Request(payload['base_url'] + '/chat/completions',
        data=json.dumps(body, allow_nan=False).encode(), headers={'Content-Type': 'application/json'}, method='POST')
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    try:
        with opener.open(request, timeout=payload['timeout_s']) as response:
            raw = response.read(MAX_RESPONSE_BYTES + 1)
            if len(raw) > MAX_RESPONSE_BYTES:
                return unknown
            text = raw.decode('utf-8')
            # Preserve the exact provider text. No content parsing or repair.
            provider_id = response.headers.get('x-request-id')
            if provider_id and (len(provider_id) > 256 or not all(32 <= ord(c) < 127 for c in provider_id)):
                provider_id = None
            return dict(outcome='completed', http_status=response.status,
                        response_text=text, provider_request_id=provider_id)
    except urllib.error.HTTPError as error:
        return dict(outcome='failed', http_status=error.code,
                    response_text=None, provider_request_id=None)
    except (OSError, TimeoutError, socket.timeout, UnicodeError, urllib.error.URLError):
        return unknown


def main():
    try:
        payload = json.loads(sys.stdin.buffer.read(2 * 1024 * 1024 + 1))
        result = execute(payload)
    except Exception:
        result = dict(outcome='outcome_unknown', http_status=None,
                      response_text=None, provider_request_id=None)
    sys.stdout.write(json.dumps(result, allow_nan=False, ensure_ascii=False))


if __name__ == '__main__':
    main()
