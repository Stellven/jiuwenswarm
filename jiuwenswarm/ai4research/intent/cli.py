"""Headless entry point with stable JSON completion and no interactive wait."""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from .bridge import CodexBridge
from .models import FrozenPolicy
from .service import IntentService
from .store import IntentStore


async def run(args):
    store = IntentStore(args.state_dir)
    if args.status:
        service = IntentService(store, None, FrozenPolicy())
        return service.get(args.status, args.owner)
    from jiuwenswarm.server.runtime.codex_subscription.service import SubscriptionService
    managed = SubscriptionService(args.subscription_root)
    service = IntentService(store, CodexBridge(managed), FrozenPolicy())
    text = args.text if args.text is not None else sys.stdin.read(65537)
    try:
        return await service.execute(text, args.owner, store.profile_id, str(args.workspace.resolve()), args.corrects)
    finally:
        await managed.transport.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-dir", type=Path, required=True, help="Local mounted evidence/SQLite directory")
    parser.add_argument("--owner", required=True, help="Explicit authorized local development identity")
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    parser.add_argument("--text", help="Original text; omitted reads bounded stdin")
    parser.add_argument("--status", help="Inspect this run without model calls")
    parser.add_argument("--corrects", help="Link a new run to a halted/paused run")
    parser.add_argument("--subscription-root", type=Path, default=Path.home() / ".jiuwenswarm-ai4r" / "subscription",
                        help="Existing application-owned managed profile (never the IDE credentials directory)")
    args = parser.parse_args()
    try:
        result = asyncio.run(run(args))
    except Exception as exc:
        code = str(exc) if str(exc) in {"EMPTY_INPUT", "INPUT_SIZE_EXCEEDED", "RUN_NOT_FOUND", "INVALID_RUN_ID", "CORRECTION_REQUIRES_HALTED_RUN", "RUNTIME_BUSY"} else "ENVIRONMENT_UNAVAILABLE"
        result = {"run_id": None, "state": "HALTED", "verdict": "ENVIRONMENT_BLOCKED", "reasons": [code],
                  "durable": False, "accepted_reference": None}
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result.get("state") == "ACCEPTED" and result.get("accepted_reference") else 2


if __name__ == "__main__":
    raise SystemExit(main())
