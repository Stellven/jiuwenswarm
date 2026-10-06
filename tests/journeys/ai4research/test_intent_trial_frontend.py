"""Built native browser journeys with actual local plumbing and scripted models.

These are explicit mock-provider UI observations. They cannot establish real
model fidelity, secured IPC/OS custody or model-backed trial acceptance.
The native dist must be built and an installed Chrome channel must be present.
"""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
import hashlib
import json
import os
from pathlib import Path
import socket
import zipfile

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from playwright.async_api import async_playwright, expect
import pytest
import uvicorn

from jiuwenswarm.ai4research.http import trial_router
from tests.fixtures.ai4research.trial_support import CASE_TEXT, OBJECTIVE, make_trial

ROOT = Path(__file__).resolve().parents[3]
DIST = ROOT / "jiuwenswarm/channels/web/frontend/dist"
PENDING = "intent-trial-pending-request"
pytestmark = pytest.mark.asyncio


@asynccontextmanager
async def native_browser(tmp_path, *, viewport=None, **bridge_options):
    assert (DIST / "index.html").is_file(), "Build the native frontend before browser verification"
    trial = make_trial(tmp_path, **bridge_options)
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.bind(("127.0.0.1", 0))
    listener.listen(16)
    port = listener.getsockname()[1]
    base = f"http://127.0.0.1:{port}"
    http = FastAPI()
    http.include_router(trial_router(trial.application, expected_origin=base))
    http.mount("/assets", StaticFiles(directory=DIST / "assets"), name="native-assets")

    @http.get("/intent-trial")
    async def page_entry():
        return FileResponse(DIST / "index.html")

    server = uvicorn.Server(uvicorn.Config(http, host="127.0.0.1", port=port,
        log_level="error", access_log=False, proxy_headers=False, lifespan="off"))
    serving = asyncio.create_task(server.serve(sockets=[listener]))
    for _ in range(500):
        if server.started:
            break
        await asyncio.sleep(0.01)
    assert server.started, "Actual loopback mock fixture service did not start"
    try:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(channel="chrome", headless=True)
            context = await browser.new_context(viewport=viewport or {"width": 1440, "height": 1000})
            page = await context.new_page()
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            await page.goto(base + "/intent-trial")
            await expect(page.get_by_test_id("intent-trial-page")).to_be_visible()
            try:
                yield trial, page, context, base, browser.version, errors
            finally:
                await context.close()
                await browser.close()
    finally:
        await trial.application.shutdown()
        server.should_exit = True
        await asyncio.wait_for(serving, 5)
        listener.close()


async def connect(page, trial):
    # This token exists only in an isolated test store and is never logged.
    await page.get_by_test_id("intent-trial-session-input").fill(trial.token)
    await page.get_by_test_id("intent-trial-connect-button").click()
    await expect(page.get_by_test_id("intent-trial-readiness")).to_have_text("Ready")


async def submit(page, text=OBJECTIVE):
    await page.get_by_test_id("intent-trial-objective-input").fill(text)
    await page.get_by_test_id("intent-trial-submit-button").click()


async def terminal_run(page, trial, status="ACCEPTED"):
    await expect(page.get_by_test_id("intent-trial-result")).to_have_attribute("data-variant", status)
    run_id = await page.get_by_test_id("intent-trial-run-id").inner_text()
    run = trial.application.project(trial.context, run_id)
    assert run["status"] == status and run["mock"] is True
    return run


async def record(page, trial, tmp_path, name, browser_version, errors, **outcomes):
    assert not errors, errors
    geometry = await page.evaluate("""() => ({
        viewport: window.innerWidth,
        document: document.documentElement.scrollWidth,
        content: document.querySelector('[data-testid="intent-trial-page"]').getBoundingClientRect().width
    })""")
    assert geometry["document"] <= geometry["viewport"], geometry
    storage = await page.evaluate("() => ({local: Object.values(localStorage), session: Object.values(sessionStorage)})")
    assert all(trial.token not in value for value in storage["local"] + storage["session"])
    output = Path(os.environ.get("AI4R_FRONTEND_ARTIFACT_DIR", str(tmp_path / "artifacts")))
    output.mkdir(parents=True, exist_ok=True)
    screenshot = output / (name + ".png")
    observed = output / (name + ".json")
    assert not screenshot.exists() and not observed.exists(), "Use a fresh immutable browser run artifact directory"
    await page.screenshot(path=screenshot, full_page=True)
    entry = DIST / "index.html"
    observation = {"case": name, "scope": "Actual native built browser/local HTTP/durable plumbing with ScriptedBridge; mock provider only",
        "real_model_acceptance": "NOT_RUN", "secured_ipc_os_custody": "NOT_ESTABLISHED",
        "browser": browser_version, "viewport": page.viewport_size, "geometry": geometry,
        "page_errors": errors, "native_entry_sha256": hashlib.sha256(entry.read_bytes()).hexdigest(),
        "screenshot_sha256": hashlib.sha256(screenshot.read_bytes()).hexdigest(),
        "scripted_invocations": len(trial.bridge.calls), "roles": [call["role"] for call in trial.bridge.calls],
        "server_runs": len(trial.application.store.list_runs(caller_id=trial.context.user_id)),
        "credential_in_browser_storage": False, "outcomes": outcomes}
    observed.write_text(json.dumps(observation, indent=2) + "\n", encoding="utf-8")


@pytest.mark.parametrize("viewport,label", [({"width": 1440, "height": 1000}, "wide"), ({"width": 390, "height": 844}, "narrow")])
async def test_native_accepted_layout_and_exact_bundle(tmp_path, viewport, label):
    async with native_browser(tmp_path, viewport=viewport) as (trial, page, _, _, version, errors):
        await connect(page, trial)
        await submit(page)
        run = await terminal_run(page, trial)
        await expect(page.get_by_test_id("intent-trial-accepted-hash")).to_have_text(run["accepted_ref"]["sha256"])
        output = json.loads(await page.get_by_test_id("intent-trial-accepted-output").inner_text())
        assert output == run["accepted_intent"]
        await expect(page.get_by_test_id("intent-trial-run-button")).to_contain_text("ACCEPTED")
        await expect(page.get_by_test_id("intent-trial-mock-label")).to_be_visible()
        assert len(trial.bridge.calls) == 2
        async with page.expect_download() as downloaded:
            await page.get_by_test_id("intent-trial-bundle-button").click()
        download = await downloaded.value
        bundle = tmp_path / "mock-bundle.zip"
        await download.save_as(bundle)
        with zipfile.ZipFile(bundle) as archive:
            exported = json.loads(archive.read("manifest.json"))
            assert exported["manifest"]["accepted_ref"] == run["accepted_ref"]
            assert all(trial.token.encode() not in archive.read(name) for name in archive.namelist())
        assert len(trial.bridge.calls) == 2
        await record(page, trial, tmp_path, "accepted-" + label, version, errors,
            accepted_ref=run["accepted_ref"], exact_output=True, exact_bundle=True, history="ACCEPTED")


async def test_native_authentication_rejection_is_confirmed_without_dispatch(tmp_path):
    async with native_browser(tmp_path) as (trial, page, _, _, version, errors):
        await page.get_by_test_id("intent-trial-session-input").fill("invalid-fixture-credential")
        await page.get_by_test_id("intent-trial-connect-button").click()
        await expect(page.get_by_test_id("intent-trial-error")).to_contain_text("policy_denied")
        await submit(page)
        await expect(page.get_by_test_id("intent-trial-error")).to_contain_text("Submission was rejected")
        assert await page.evaluate("key => localStorage.getItem(key)", PENDING) is None
        assert trial.bridge.calls == []
        assert trial.application.store.list_runs(caller_id=trial.context.user_id) == []
        await record(page, trial, tmp_path, "authentication-rejected", version, errors,
            confirmed_rejection=True, no_pending_identity=True, no_dispatch=True)


async def test_native_refusal_attention_and_corrected_predecessor(tmp_path):
    async with native_browser(tmp_path, viewport={"width": 390, "height": 844}, variant="omission") as (trial, page, _, _, version, errors):
        await connect(page, trial)
        await submit(page, CASE_TEXT["omission"])
        refused = await terminal_run(page, trial, "FAILED")
        await expect(page.get_by_test_id("intent-trial-reason")).to_be_visible()
        await expect(page.get_by_test_id("intent-trial-attention")).to_be_visible()
        await expect(page.get_by_test_id("intent-trial-accepted-output")).to_have_count(0)
        await expect(page.get_by_test_id("intent-trial-run-button")).to_contain_text("FAILED")
        await record(page, trial, tmp_path, "refused-narrow", version, errors,
            refusal_visible=True, attention_visible=True, accepted_output_absent=True)
        trial.bridge.variant, trial.bridge.failed_check = "faithful", None
        await submit(page, OBJECTIVE)
        corrected = await terminal_run(page, trial)
        assert corrected["run_id"] != refused["run_id"]
        assert corrected["predecessor_run_id"] == refused["run_id"]
        assert trial.application.project(trial.context, refused["run_id"])["status"] == "FAILED"
        assert len(trial.bridge.calls) == 4
        await record(page, trial, tmp_path, "corrected-after-refusal", version, errors,
            predecessor_retained=True, old_failure_retained=True, distinct_corrected_run=True)


@pytest.mark.parametrize("failure", ["lost_response", "server_503"])
async def test_native_uncertain_submit_reload_only_retrieves(tmp_path, failure):
    async with native_browser(tmp_path) as (trial, page, _, _, version, errors):
        await connect(page, trial)
        delivered = []
        async def uncertain(route):
            if route.request.method != "POST":
                await route.continue_()
                return
            delivered.append(route.request.post_data_json["client_request_id"])
            response = await route.fetch()
            assert response.status == 202
            if failure == "lost_response":
                await route.abort("connectionfailed")
            else:
                await route.fulfill(status=503, content_type="application/json", body=json.dumps({"detail": {"code": "fixture_response_lost"}}))
        await page.route("**/api/intent-trial/runs", uncertain)
        await submit(page)
        await expect(page.get_by_test_id("intent-trial-error")).to_contain_text("Submission may be unconfirmed")
        pending = await page.evaluate("key => localStorage.getItem(key)", PENDING)
        assert pending == delivered[0]
        runs = trial.application.store.list_runs(caller_id=trial.context.user_id)
        assert len(runs) == 1
        run_id = runs[0]["run_id"]
        await trial.finish(run_id)
        await record(page, trial, tmp_path, "uncertain-" + failure, version, errors,
            pending_retained=True, posted_requests=1, server_runs=1)
        await page.reload()
        await expect(page.get_by_test_id("intent-trial-session-input")).to_have_value("")
        assert await page.evaluate("key => localStorage.getItem(key)", PENDING) == pending
        await connect(page, trial)
        reconciled = await terminal_run(page, trial)
        assert reconciled["run_id"] == run_id
        assert await page.evaluate("key => localStorage.getItem(key)", PENDING) is None
        assert len(delivered) == 1 and len(trial.bridge.calls) == 2
        await record(page, trial, tmp_path, "reconciled-" + failure, version, errors,
            same_run=True, posted_requests=1, no_replay=True, token_not_persisted=True)


async def test_native_unresolved_pending_requires_explicit_fresh_correction(tmp_path):
    async with native_browser(tmp_path, variant="omission") as (trial, page, _, _, version, errors):
        await connect(page, trial)
        await submit(page, CASE_TEXT["omission"])
        predecessor = await terminal_run(page, trial, "FAILED")
        async def undelivered(route):
            if route.request.method == "POST":
                await route.abort("connectionfailed")
            else:
                await route.continue_()
        await page.route("**/api/intent-trial/runs", undelivered)
        await submit(page, "Corrected objective before an intentionally lost request.")
        await expect(page.get_by_test_id("intent-trial-pending-request")).to_be_visible()
        await page.get_by_test_id("intent-trial-submit-button").click()
        await expect(page.get_by_test_id("intent-trial-fresh-button")).to_be_visible()
        assert len(trial.application.store.list_runs(caller_id=trial.context.user_id)) == 1
        assert len(trial.bridge.calls) == 2
        await record(page, trial, tmp_path, "pending-not-found", version, errors,
            retrieve_only=True, old_failure_retained=True, explicit_fresh_action=True)
        await page.get_by_test_id("intent-trial-fresh-button").click()
        assert await page.evaluate("key => localStorage.getItem(key)", PENDING) is None
        assert len(trial.bridge.calls) == 2
        await page.unroute("**/api/intent-trial/runs", undelivered)
        trial.bridge.variant, trial.bridge.failed_check = "faithful", None
        await submit(page, OBJECTIVE)
        corrected = await terminal_run(page, trial)
        assert corrected["predecessor_run_id"] == predecessor["run_id"]
        assert corrected["client_request_id"] != predecessor["client_request_id"]
        assert trial.application.project(trial.context, predecessor["run_id"])["status"] == "FAILED"
        assert len(trial.bridge.calls) == 4
        await record(page, trial, tmp_path, "fresh-after-unresolved", version, errors,
            explicit_new_request=True, predecessor_retained=True, old_failure_retained=True)


async def test_native_browser_disconnect_preserves_work_and_reconnects(tmp_path):
    async with native_browser(tmp_path, wait_role="compiler") as (trial, page, context, base, version, errors):
        await connect(page, trial)
        await submit(page)
        await asyncio.wait_for(trial.bridge.entered.wait(), 5)
        run_id = trial.application.store.list_runs(caller_id=trial.context.user_id)[0]["run_id"]
        await page.close()
        assert trial.application.project(trial.context, run_id)["status"] == "COMPILING"
        trial.bridge.release.set()
        original = await trial.finish(run_id)
        assert original["status"] == "ACCEPTED"
        page = await context.new_page()
        await page.goto(base + "/intent-trial")
        await connect(page, trial)
        await page.get_by_test_id("intent-trial-run-button").click()
        restored = await terminal_run(page, trial)
        assert restored["run_id"] == original["run_id"] and restored["accepted_ref"] == original["accepted_ref"]
        assert len(trial.bridge.calls) == 2
        await record(page, trial, tmp_path, "reconnected-after-disconnect", version, errors,
            no_implicit_cancel=True, no_replay=True, same_accepted_ref=True)


async def test_native_explicit_cancel_is_visible_and_nonreplaying(tmp_path):
    async with native_browser(tmp_path, wait_role="compiler") as (trial, page, _, _, version, errors):
        await connect(page, trial)
        await submit(page)
        await asyncio.wait_for(trial.bridge.entered.wait(), 5)
        await expect(page.get_by_test_id("intent-trial-cancel-button")).to_be_visible()
        await page.get_by_test_id("intent-trial-cancel-button").click()
        cancelled = await terminal_run(page, trial, "CANCELLED")
        await expect(page.get_by_test_id("intent-trial-run-button")).to_contain_text("CANCELLED")
        await expect(page.get_by_test_id("intent-trial-accepted-output")).to_have_count(0)
        assert cancelled["accepted_ref"] is None and len(trial.bridge.calls) == 1
        await record(page, trial, tmp_path, "explicitly-cancelled", version, errors,
            explicit_cancellation=True, accepted_output_absent=True, no_replay=True)
