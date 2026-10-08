"""Signed-out smoke of production service; never initiates login/model work."""
import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from jiuwenswarm.server.runtime.codex_subscription.service import SubscriptionService
from jiuwenswarm.server.runtime.codex_subscription.transport import CodexError


async def main():
    evidence = Path(os.environ["LOCALAPPDATA"]) / "ai4r-tools/evidence/AI4R-001"
    evidence.mkdir(parents=True, exist_ok=True)
    root = Path(tempfile.mkdtemp(prefix="m1-product-smoke-", dir=evidence))
    service = SubscriptionService(root)
    other = SubscriptionService(root)
    summary = {"profile": str(root), "cycles": []}
    try:
        for _ in range(2):
            state = await service.status()
            assert state["state"] == "signed_out"
            try:
                await other.status()
            except CodexError as exc:
                assert str(exc) == "PROFILE_IN_USE"
            else:
                raise AssertionError("Second owner was admitted")
            await service.transport.close()
            summary["cycles"].append({"state": state["state"], "second_owner_blocked": True, "closed": service.transport.process is None})
    finally:
        await service.transport.close()
        await other.transport.close()
    (root / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary))


if __name__ == "__main__":
    asyncio.run(main())
