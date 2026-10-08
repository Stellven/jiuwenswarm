"""Real native HTTP/proxy/ChatPanel browser check; model is a frozen fixture.

This proves the local native boundary, not subscription availability or complete
application onboarding. Its explicit profile/session context is a UI fixture.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from playwright.sync_api import sync_playwright

from jiuwenswarm.ai4research.intent.models import InvocationEvidence, sha256_text
from jiuwenswarm.ai4research.intent.service import IntentService
from jiuwenswarm.ai4research.intent.store import IntentStore
from jiuwenswarm.gateway.channel_manager.web.intent_http import LocalIntentContext, register_intent_routes
from tests.unit_tests.ai4research.test_intent_gate import ORIGINAL, candidate_fixture, assessment_fixture


class BrowserModelFixture:
    def __init__(self):
        self.outputs = {}

    async def invoke(self, role, prompt, run_id, policy):
        original = json.loads(prompt.split("Original input: ", 1)[1].split("\nExact candidate:", 1)[0])
        if role == "compiler":
            candidate = candidate_fixture()
            candidate.update(run_id=run_id, input_sha256=sha256_text(original))
            raw = "{" if "deficient" in original else json.dumps(candidate)
            self.outputs[run_id] = raw
        else:
            assessment = assessment_fixture(self.outputs[run_id])
            assessment.update(run_id=run_id, input_sha256=sha256_text(original))
            raw = json.dumps(assessment)
        await asyncio.sleep(0.02)
        return InvocationEvidence(invocation_id=role + run_id, role=role, run_id=run_id,
                                  conversation_id=role + run_id, prompt_sha256=sha256_text(prompt),
                                  status="completed", elapsed_seconds=0.02, raw_output=raw)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", type=Path, required=True)
    args = parser.parse_args()
    evidence = args.evidence.resolve()
    evidence.mkdir(parents=True, exist_ok=True)
    repo = Path(__file__).resolve().parents[3]
    frontend = repo / "jiuwenswarm/channels/web/frontend"
    token = "public-test-fixture-credential-0123456789"
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        service = IntentService(IntentStore(root), BrowserModelFixture())
        app = FastAPI()
        context = LocalIntentContext(token, "browser-owner", "browser-profile", "browser-workspace", root,
                                     "__wsdt5179", (5179, 19090))
        register_intent_routes(app, service=service, context=context)
        server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=19090, log_level="warning"))
        thread = threading.Thread(target=server.run, daemon=True)
        thread.start()
        environment = dict(os.environ)
        environment["JIUWENSWARM_DESKTOP_TOKEN"] = token
        environment["FRONTEND_PORT"] = "5179"
        environment["WEB_PORT"] = "19090"
        proxy_log = (evidence / "native-proxy.log").open("w", encoding="utf-8")
        command = [sys.executable, "-m", "jiuwenswarm.channels.web.app_web", "--host", "127.0.0.1", "--port", "5179",
                   "--dist", str(frontend / "dist/intent-browser"), "--proxy-target", "http://127.0.0.1:19090"]
        process = subprocess.Popen(command, cwd=repo, env=environment, stdout=proxy_log, stderr=proxy_log,
                                   creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        try:
            import urllib.request
            for _ in range(100):
                try:
                    urllib.request.urlopen("http://127.0.0.1:5179/", timeout=0.1)
                    break
                except Exception:
                    if process.poll() is not None:
                        raise RuntimeError("Native proxy exited; inspect native-proxy.log")
                    time.sleep(0.1)
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(executable_path="C:/Program Files/Google/Chrome/Application/chrome.exe", headless=True)
                page = browser.new_page(viewport={"width": 1440, "height": 1080})
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.on("response", lambda response: print("intent-http", response.status, response.url) if "/api/intent" in response.url else None)
                # Native credential exchange is the SPA entry; fixture HTML is
                # a separately served static file, so enter the native gate first.
                page.goto(f"http://127.0.0.1:5179/?dt={token}", wait_until="domcontentloaded")
                page.goto("http://127.0.0.1:5179/tests/fixtures/intent/index.html", wait_until="networkidle")
                page.get_by_test_id("chat-panel-intent-toggle").wait_for()
                native_styles = page.evaluate("""(() => {
                    const root = document.documentElement;
                    const composer = document.querySelector('.chat-input-container');
                    return {theme:root.dataset.theme,colorMode:root.dataset.colorMode,
                            surface:getComputedStyle(root).getPropertyValue('--color-surface-page').trim(),
                            bodyFont:getComputedStyle(document.body).fontFamily,
                            composerBackground:composer && getComputedStyle(composer).backgroundColor,
                            cssResources:[...document.styleSheets].map(sheet=>sheet.href).filter(Boolean)};
                })()""")
                assert native_styles["theme"] == "default" and native_styles["colorMode"] == "light"
                assert native_styles["surface"] and native_styles["cssResources"], native_styles
                assert native_styles["composerBackground"] not in {None, "rgba(0, 0, 0, 0)"}, native_styles
                editor = page.locator('[contenteditable="true"]').first
                editor.fill("Ordinary text conversation")
                page.get_by_test_id("chat-panel-input-send").click()
                page.wait_for_function("window.ordinaryMessage === 'Ordinary text conversation'")
                page.get_by_test_id("chat-panel-intent-toggle").check()
                original = "  " + ORIGINAL.replace(" Never use network.", "\nNever use network.") + "  "
                editor.fill(original)
                page.get_by_test_id("chat-panel-input-send").click()
                try:
                    page.wait_for_function("document.querySelector('[data-testid=chat-panel-intent-verdict]')?.textContent.includes('PASS')", timeout=10000)
                except Exception:
                    page.screenshot(path=str(evidence / "native-first-failure.png"), full_page=True)
                    print(page.locator('[data-testid="chat-panel-intent-controls"]').inner_text(), flush=True)
                    print("browser-errors", errors, flush=True)
                    raise
                accepted_id = page.get_by_test_id("chat-panel-intent-run-id").inner_text().split("：")[-1].split(": ")[-1]
                retained_original = (service.store.artifact_root / accepted_id / "original.txt").read_text(encoding="utf-8")
                print("native-original", repr(retained_original), "expected", repr(original), flush=True)
                assert retained_original == original, "Native InputArea changed original input"
                page.get_by_test_id("chat-panel-intent-output-toggle").click()
                page.screenshot(path=str(evidence / "native-accepted-wide.png"), full_page=True)
                page.reload(wait_until="networkidle")
                page.wait_for_function("document.querySelector('[data-testid=chat-panel-intent-verdict]')?.textContent.includes('PASS')")
                assert accepted_id in page.get_by_test_id("chat-panel-intent-run-id").inner_text()
                page.get_by_test_id("chat-panel-intent-toggle").check()
                editor = page.locator('[contenteditable="true"]').first
                editor.fill("Research deficient fixture")
                page.get_by_test_id("chat-panel-input-send").click()
                page.wait_for_function("document.querySelector('[data-testid=chat-panel-intent-verdict]')?.textContent.includes('FAIL')")
                assert page.get_by_test_id("chat-panel-intent-reason").count() > 0
                halted_id = re.search(r"[0-9a-f]{32}", page.get_by_test_id("chat-panel-intent-run-id").inner_text()).group()
                page.screenshot(path=str(evidence / "native-halted-wide.png"), full_page=True)
                page.set_viewport_size({"width": 390, "height": 844})
                narrow_layout = page.evaluate("({viewport:innerWidth,document:document.documentElement.scrollWidth,minWidth:getComputedStyle(document.documentElement).minWidth})")
                page.screenshot(path=str(evidence / "native-halted-narrow.png"), full_page=True)
                page.get_by_test_id("chat-panel-intent-correct").click()
                editor.fill(ORIGINAL)
                page.get_by_test_id("chat-panel-input-send").click()
                page.wait_for_function("document.querySelector('[data-testid=chat-panel-intent-verdict]')?.textContent.includes('PASS')")
                corrected_id = re.search(r"[0-9a-f]{32}", page.get_by_test_id("chat-panel-intent-run-id").inner_text()).group()
                assert service.get(corrected_id, "browser-owner")["corrects_run_id"] == halted_id
                page.screenshot(path=str(evidence / "native-corrected-narrow.png"), full_page=True)
                page.set_viewport_size({"width": 584, "height": 844})
                page.evaluate("localStorage.setItem('i18nextLng','en')")
                page.reload(wait_until="networkidle")
                page.wait_for_function("document.querySelector('[data-testid=chat-panel-intent-verdict]')?.textContent.includes('PASS')")
                assert page.get_by_test_id("chat-panel-intent-label").inner_text() == "Compile and verify research intent"
                controls = page.get_by_test_id("chat-panel-intent-controls").bounding_box()
                assert controls["x"] >= 0 and controls["x"] + controls["width"] <= 584
                page.screenshot(path=str(evidence / "native-accepted-minimum-en.png"), full_page=True)
                assert all(error == "WebSocket 连接异常" for error in errors), errors
                fixture_files = [Path(__file__), repo / "tests/unit_tests/ai4research/test_intent_gate.py", frontend / "tests/fixtures/intent/main.tsx", frontend / "tests/fixtures/intent/vite.config.ts", frontend / "tests/fixtures/intent/index.html"]
                receipts = {run_id: service.get(run_id, "browser-owner") for run_id in (accepted_id, halted_id, corrected_id)}
                configurations = {run_id: json.loads((service.store.artifact_root / run_id / "configuration.json").read_text(encoding="utf-8")) for run_id in receipts}
                result = {"result": "PASS", "browser": browser.version, "assertions": ["ordinary_chat_unchanged", "protected_native_proxy_cookie", "exact_original_text", "accepted_intent_inspection", "reload_same_run", "visible_halt", "linked_correction", "wide_narrow", "english_at_native_minimum_width", "native_theme_and_css_resources"],
                          "fixture_sha256": {str(path.relative_to(repo)).replace("\\", "/"): hashlib.sha256(path.read_bytes()).hexdigest() for path in fixture_files},
                          "ports": {"native_frontend": 5179, "protected_backend": 19090}, "narrow_layout": narrow_layout, "native_styles": native_styles,
                          "fixture_run_receipts": receipts, "source_configurations": configurations,
                          "dependency_mode": "real native proxy + FastAPI/SQLite/gate + frozen model fixture", "limitations": ["application account/session context supplied by fixture; unrelated native WebSocket calls unavailable", "real model campaign separate", "Chrome 107 runtime not available", "existing global HTML minimum width is 584px; 390px screenshots retain native horizontal overflow"]}
                (evidence / "native-browser-result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
                print(json.dumps(result))
                browser.close()
        finally:
            process.terminate()
            process.wait(timeout=10)
            proxy_log.close()
            server.should_exit = True
            thread.join(timeout=10)


if __name__ == "__main__":
    main()
