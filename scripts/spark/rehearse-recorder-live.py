#!/usr/bin/env python3
"""Verify a real recorder evidence Launch from Chromium on the demo tailnet."""
import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path
import time

from playwright.async_api import async_playwright, expect


URL = 'http://100.105.127.48:5173'
TEMPLATE = 'recorder-evidence-walkthrough'
CHECKPOINTS = ('report-pinned', 'parity-checked', 'deepseek-trace-checked', 'granite-traces-checked', 'verification-complete')


async def run():
    output = Path.home() / 'predemo-spark/OPS/ui-shots/live-launch'
    output.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True, args=['--no-sandbox'])
        page = await browser.new_page(viewport={'width': 1440, 'height': 1000})
        errors, api_errors = [], []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.on('response', lambda response: api_errors.append((response.status, response.url))
                if '/api/factory/' in response.url and response.status >= 400 else None)
        await page.goto(URL, wait_until='networkidle')
        skip = page.get_by_role('button', name='跳过', exact=True)
        if await skip.count():
            await skip.click()
        await page.locator('[data-testid="session-sidebar-nav-item"][data-variant="factoryRuns"]').click()
        await page.get_by_test_id('factory-runs-launch-button').click()
        await page.get_by_test_id('factory-runs-launch-template').select_option(TEMPLATE)
        await page.screenshot(path=str(output / '01-template.png'))
        started = time.monotonic()
        async with page.expect_response(lambda response: response.url.endswith('/api/factory/launch') and response.request.method == 'POST') as pending:
            await page.get_by_test_id('factory-runs-launch-confirm').click()
        response = await pending.value
        assert response.status == 202, await response.text()
        launch = await response.json()
        status = page.get_by_test_id('factory-runs-session-status')
        await expect(status).to_have_attribute('data-variant', 'running', timeout=30_000)
        await expect(page.get_by_test_id('factory-runs-live')).to_be_checked()
        detected = []
        for checkpoint in CHECKPOINTS:
            await page.locator(f'[data-testid="factory-runs-event"][data-variant="{checkpoint}"]').wait_for(timeout=75_000)
            detected.append(dict(checkpoint=checkpoint, observed_after_s=round(time.monotonic() - started, 3)))
            if checkpoint == 'deepseek-trace-checked':
                await page.screenshot(path=str(output / '02-running.png'))
        await expect(status).to_have_attribute('data-variant', 'finished', timeout=30_000)
        await expect(page.get_by_test_id('factory-runs-session-message')).to_contain_text('Verification complete.')
        await page.screenshot(path=str(output / '03-finished.png'))
        factory = URL + '/api/factory/runs/' + launch['id']
        session = await (await page.request.get(factory + '/session')).json()
        detail = await (await page.request.get(factory)).json()
        receipt, = [row for row in detail['files'] if 'recorder-evidence-verification.json' in row.get('artifact_ids', [])]
        assert receipt['integrity'] == 'verified' and session['status'] == 'finished'
        assert not errors and not api_errors, (errors, api_errors)
        result = dict(rehearsed_utc=datetime.now(timezone.utc).isoformat(), url=URL, template=TEMPLATE, launch=launch,
                      session=session, observations=detected, receipt=receipt, page_errors=errors, factory_api_errors=api_errors)
        (output / 'rehearsal.json').write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps(result, indent=2))
        await browser.close()


if __name__ == '__main__':
    asyncio.run(run())
