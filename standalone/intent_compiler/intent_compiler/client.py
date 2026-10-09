"""Finite headless ordinary client for M0-IF-001@r1; no workflow authority."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import time
import uuid

import httpx

VERSION = "1.0.0"
TERMINAL = {"completed", "halted", "blocked", "cancelled", "paused", "rejected"}
STATUS_FIELDS = {"schema_version", "id", "client_request_id", "run_id", "revision", "stage", "status", "candidate_refs", "accepted_refs", "decision_ref", "reasons", "bundle_ref"}


class ClientError(RuntimeError):
    def __init__(self, message, detail=None, status_code=None):
        super().__init__(message)
        self.detail = detail or {"category": "client_error", "message": message}
        self.status_code = status_code


class CompilerClient:
    def __init__(self, url, token, account_id="local-user", workspace_id="local-workspace", transport=None):
        self.account_id, self.workspace_id = account_id, workspace_id
        self.http = httpx.Client(base_url=url.rstrip("/"), timeout=15, transport=transport,
                                 headers={"Authorization": "Bearer " + token,
                                          "X-Account-ID": account_id, "X-Workspace-ID": workspace_id})

    def close(self):
        self.http.close()

    def _json(self, method, path, **kwargs):
        response = self.http.request(method, path, **kwargs)
        try:
            data = response.json()
        except ValueError as exc:
            detail = {"category": "server_response_invalid", "message": "The server returned an unavailable or malformed JSON contract.",
                      "http_status": response.status_code}
            raise ClientError(detail["message"], detail, response.status_code) from exc
        if response.status_code >= 400:
            raise ClientError(data.get("message", "Client operation rejected"), data, response.status_code)
        return data

    def readiness(self, expected_instance_id=None, expected_build_id=None):
        data = self._json("GET", "/api/v1/readiness")
        required = {"schema_version", "id", "client_contract_version", "instance_id", "build_id", "operations", "prerequisites", "ready"}
        if not required.issubset(data) or data["client_contract_version"] != VERSION or data["schema_version"] != VERSION:
            raise ClientError("Unsupported or incomplete readiness contract")
        if expected_instance_id and data["instance_id"] != expected_instance_id:
            raise ClientError("Wrong application instance")
        if expected_build_id and data["build_id"] != expected_build_id:
            raise ClientError("Wrong application build")
        return data

    def submit(self, request, *, client_request_id, documents=None, resources=None, profile_id="compiler-only",
               input_directory=None, requested_seed=None, previous_run_id=None, readiness=None):
        readiness = readiness or self.readiness()
        if not readiness["ready"]:
            raise ClientError("Execution prerequisites unavailable", {"category": "prerequisite_unavailable", "prerequisites": readiness["prerequisites"]})
        if profile_id not in readiness.get("ext", {}).get("m0.intent", {}).get("profiles", []):
            raise ClientError("Selected profile is not operator-approved")
        payload = {"schema_version": VERSION, "id": "submission-" + client_request_id,
                   "client_request_id": client_request_id, "account_id": self.account_id,
                   "workspace_id": self.workspace_id, "profile_id": profile_id,
                   "expected_instance_id": readiness["instance_id"], "expected_build_id": readiness["build_id"],
                   "client_contract_version": VERSION, "request": request,
                   "documents": documents or [], "resources": resources or [], "input_directory": input_directory,
                   "requested_seed": requested_seed, "previous_run_id": previous_run_id}
        try:
            return self._status(self._json("POST", "/api/v1/runs", json=payload))
        except httpx.TransportError:
            # Ambiguous delivery is reconciled once. Never automatically resubmit.
            return self.reconcile(client_request_id)

    def _status(self, data):
        if not STATUS_FIELDS.issubset(data) or data["schema_version"] != VERSION:
            raise ClientError("Malformed or incompatible status contract")
        return data

    def status(self, run_id):
        return self._status(self._json("GET", "/api/v1/runs/" + run_id))

    def reconcile(self, request_id):
        return self._status(self._json("GET", "/api/v1/requests/" + request_id))

    def wait(self, run_id, timeout=600, poll_interval=0.25):
        deadline = time.monotonic() + timeout
        revision = -1
        while True:
            data = self.status(run_id)
            if data["revision"] < revision:
                raise ClientError("Status revision decreased; completion is unavailable")
            revision = data["revision"]
            if data["status"] in TERMINAL:
                return data
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise ClientError("Finite client wait expired; the server-owned run remains inspectable", {"category": "client_timeout", "run_id": run_id})
            time.sleep(min(poll_interval, remaining))

    def cancel(self, run_id, request_id=None):
        request_id = request_id or uuid.uuid4().hex
        return self._json("POST", "/api/v1/runs/" + run_id + "/cancel",
                          json={"schema_version": VERSION, "id": "cancel-" + request_id,
                                "request_id": request_id, "run_id": run_id})

    def export(self, run_id, destination):
        response = self.http.get("/api/v1/runs/" + run_id + "/bundle")
        if response.status_code >= 400:
            try:
                detail = response.json()
            except ValueError:
                detail = {"category": "export_unavailable", "message": "The evidence export returned an unavailable or malformed error response.",
                          "run_id": run_id, "http_status": response.status_code}
            raise ClientError("Evidence export failed", detail, response.status_code)
        path = Path(destination)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(response.content)
        return str(path)

    def result(self, run_id):
        return self._json("GET", "/api/v1/runs/" + run_id + "/result")


def cli(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:5173")
    parser.add_argument("--token-file", default=os.getenv("INTENT_AUTH_TOKEN_FILE"))
    parser.add_argument("--account-id", default=os.getenv("INTENT_ACCOUNT_ID", "local-user"))
    parser.add_argument("--workspace-id", default=os.getenv("INTENT_WORKSPACE_ID", "local-workspace"))
    commands = parser.add_subparsers(dest="operation", required=True)
    commands.add_parser("readiness")
    run = commands.add_parser("run")
    request = run.add_mutually_exclusive_group(required=True)
    request.add_argument("--request")
    request.add_argument("--request-file")
    run.add_argument("--client-request-id", required=True)
    run.add_argument("--profile", default="compiler-only")
    run.add_argument("--documents-json", default="[]")
    run.add_argument("--resources-json", default="[]")
    run.add_argument("--input-directory")
    run.add_argument("--seed", type=int)
    run.add_argument("--previous-run-id")
    run.add_argument("--timeout", type=float, default=600)
    run.add_argument("--export", required=True)
    for name in ["status", "cancel", "result", "export"]:
        sub = commands.add_parser(name)
        sub.add_argument("run_id")
        if name == "export":
            sub.add_argument("destination")
    reconcile = commands.add_parser("reconcile")
    reconcile.add_argument("client_request_id")
    args = parser.parse_args(argv)
    token = Path(args.token_file).read_text(encoding="utf-8").strip() if args.token_file else os.getenv("INTENT_AUTH_TOKEN", "")
    client = CompilerClient(args.url, token, args.account_id, args.workspace_id)
    try:
        if args.operation == "readiness":
            data = client.readiness()
            result = 0 if data["ready"] else 3
        elif args.operation == "run":
            if args.timeout <= 0:
                raise ClientError("Headless timeout must be positive")
            text = Path(args.request_file).read_bytes().decode("utf-8") if args.request_file else args.request
            submitted = client.submit(text, client_request_id=args.client_request_id,
                profile_id=args.profile, documents=json.loads(args.documents_json), resources=json.loads(args.resources_json),
                input_directory=args.input_directory, requested_seed=args.seed, previous_run_id=args.previous_run_id)
            data = client.wait(submitted["run_id"], timeout=args.timeout)
            data["local_bundle_path"] = client.export(submitted["run_id"], args.export)
            result = 0 if data["status"] == "completed" else 2
        elif args.operation == "reconcile":
            data, result = client.reconcile(args.client_request_id), 0
        elif args.operation == "export":
            data, result = {"local_bundle_path": client.export(args.run_id, args.destination)}, 0
        else:
            data, result = getattr(client, args.operation)(args.run_id), 0
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return result
    except ClientError as exc:
        data = exc.detail
        if args.operation == "run" and data.get("run_id") and data.get("category") != "export_unavailable":
            try:
                data["local_bundle_path"] = client.export(data["run_id"], args.export)
            except (ClientError, httpx.TransportError):
                data["export_unavailable"] = True
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return 4 if data.get("category") == "client_timeout" else 3
    except (httpx.TransportError, OSError, ValueError) as exc:
        print(json.dumps({"category": "client_transport_or_input", "message": str(exc)}))
        return 5
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(cli())
