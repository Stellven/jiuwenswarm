#!/usr/bin/env python3
"""Real browser replay/live smoke; synthetic live evidence, no agent/model launch."""
import asyncio
from pathlib import Path
import time

from playwright.async_api import async_playwright
from jiuwenswarm.factory.store import Store


async def main():
    base = Path.home() / 'predemo-spark'
    task_id = 'synthetic-ui-smoke-' + str(time.time_ns())
    home = base / 'factory-runs' / task_id
    with Store(home) as store:
        store.create_task(dict(task_id=task_id, objective='Synthetic UI smoke only; not model or benchmark evidence', budget={}))
        store.append_observation(task_id, dict(kind='synthetic_ui_check', values={'message': 'Synthetic first event'}))
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True, args=['--no-sandbox'])
        page = await browser.new_page(viewport={'width': 1440, 'height': 1000})
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        await page.goto('http://100.105.127.48:5173', wait_until='networkidle')
        # Fresh isolated app workspaces offer model setup; factory reads need no model.
        skip = page.get_by_role('button', name='跳过', exact=True)
        if await skip.count():
            await skip.click()
        await page.locator('[data-testid="session-sidebar-nav-item"][data-variant="factoryRuns"]').click()
        await page.get_by_test_id('factory-runs-run-title').wait_for()
        actual_bundle = page.get_by_test_id('factory-runs-run').filter(has_text='spark-prefill-factory-002').first
        await actual_bundle.click()
        await page.get_by_test_id('factory-runs-position').wait_for()
        scrubber = page.get_by_test_id('factory-runs-scrubber')
        await scrubber.fill('0')
        assert await page.get_by_test_id('factory-runs-event').count() == 0
        await page.get_by_test_id('factory-runs-play').click()
        await page.wait_for_function("document.querySelector('[data-testid=factory-runs-position]').textContent.split('/')[0].trim() !== '0'")
        await page.get_by_test_id('factory-runs-play').click()
        await page.locator('[data-testid="factory-runs-panel-tab"][data-variant="report"]').click()
        report_files = page.get_by_test_id('factory-runs-file')
        if await report_files.count():
            await report_files.first.click()
            await page.get_by_test_id('factory-runs-file-content').get_by_test_id('factory-runs-digest').wait_for()
        await page.screenshot(path=str(base / 'logs/p2-replay-smoke.png'), full_page=True)
        await page.get_by_test_id('factory-runs-run').filter(has_text=task_id).click()
        await page.locator('[data-testid="factory-runs-panel-tab"][data-variant="overview"]').click()
        await page.get_by_test_id('factory-runs-live').check()
        with Store(home) as store:
            store.append_observation(task_id, dict(kind='synthetic_ui_check', values={'message': 'Synthetic live follow event'}))
        await page.get_by_test_id('factory-runs-event').filter(has_text='Synthetic live follow event').wait_for(timeout=15000)
        assert not errors, errors
        print(f'PASS real bundle replay, scrubber, report/digest, synthetic live follow; {home}; zero JS errors')
        await browser.close()


if __name__ == '__main__':
    asyncio.run(main())
