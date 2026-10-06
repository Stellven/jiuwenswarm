"""Sequential ordinary client; no prompts, provider calls or gate authority."""
from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import quote, urlsplit

from .application import TERMINAL


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Never forward a scoped session credential or replay a submission."""

    def redirect_request(self, request, response, code, message, headers, target):
        return None


def request_json(base, token, path, payload=None):
    headers = {"Authorization": "Bearer " + token}
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    if data is not None:
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(base + "/api/intent-trial" + path, data=data, headers=headers)
    # The endpoint is local; ambient proxy configuration and redirects cannot
    # select another credential audience or turn an uncertain POST into a retry.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())
    with opener.open(request, timeout=10) as reply:
        return json.load(reply)


def run_client(*, base, token, text, request_id, timeout_seconds=400, predecessor=None):
    parsed = urlsplit(base)
    if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"} or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in {"", "/"}:
        return 3, {"code": "invalid_endpoint", "message": "Headless access requires the local application endpoint."}
    base = base.rstrip("/")
    try:
        payload = {"original_text": text, "client_request_id": request_id,
                   "options": {"mode": "headless"}, "predecessor_run_id": predecessor}
        try:
            run = request_json(base, token, "/runs", payload)
        except urllib.error.HTTPError as exc:
            status = exc.code
            exc.close()
            if 500 <= status <= 599:
                # A server error can follow committed intake. Retrieve this
                # exact identity once; never POST again or claim rejection.
                run = request_json(base, token, "/requests/" + quote(request_id, safe=""))
            else:
                return 3, {"code": "redirect_denied" if 300 <= status <= 399 else "submission_rejected",
                           "client_request_id": request_id, "http_status": status}
        except (TimeoutError, OSError, urllib.error.URLError):
            # Read-only reconciliation; never resend an uncertain submission.
            run = request_json(base, token, "/requests/" + quote(request_id, safe=""))
        deadline = time.monotonic() + timeout_seconds
        while run["status"] not in TERMINAL:
            if time.monotonic() >= deadline:
                return 3, {"code": "client_timeout", "run_id": run["run_id"], "message": "Inspection can continue; no replay was attempted."}
            time.sleep(0.25)
            run = request_json(base, token, "/runs/" + run["run_id"])
        return (0 if run["status"] == "ACCEPTED" else 2), run
    except (OSError, ValueError, KeyError, urllib.error.URLError):
        return 3, {"code": "client_unavailable", "client_request_id": request_id,
                   "message": "Submit outcome may be unknown; reconcile this identity before any new submission."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="http://127.0.0.1:4311")
    parser.add_argument("--token-file", type=Path, required=True)
    parser.add_argument("--text-file", type=Path, required=True)
    parser.add_argument("--request-id", required=True)
    parser.add_argument("--predecessor")
    args = parser.parse_args()
    try:
        token = args.token_file.read_text(encoding="utf-8").strip()
        text = args.text_file.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        print(json.dumps({"code": "input_unavailable"}))
        return 3
    code, result = run_client(base=args.base, token=token, text=text, request_id=args.request_id, predecessor=args.predecessor)
    print(json.dumps(result, ensure_ascii=False))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
