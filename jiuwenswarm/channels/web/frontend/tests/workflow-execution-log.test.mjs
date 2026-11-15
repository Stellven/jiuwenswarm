import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import JSZip from 'jszip';
import { JSDOM } from 'jsdom';
import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { projectReplay } from '../src/features/workflowDemo/replayProjection.js';
import { ExecutionLog } from '../node_modules/.cache/factory-ui/ExecutionLog.js';

const archive = await JSZip.loadAsync(
  await readFile(new URL('../../../../../docs/code/Missions/software-factory/recordings/core.zip', import.meta.url)),
);
const manifest = JSON.parse(await archive.file('manifest.json').async('string'));
const run = JSON.parse(await archive.file('blobs/' + manifest.provenance.run_sha256).async('string'));
const events = (await archive.file('blobs/' + manifest.provenance.events_sha256).async('string'))
  .trim()
  .split('\n')
  .map((line) => JSON.parse(line));

async function artifactText(artifact) {
  return archive.file(manifest.path_map[artifact.path].blob).async('string');
}

async function withLog(callback) {
  const dom = new JSDOM('<div id="root"></div>', { url: 'http://localhost:5175/?view=workflow' });
  const globals = ['window', 'document', 'navigator', 'HTMLElement', 'Event', 'MouseEvent', 'IS_REACT_ACT_ENVIRONMENT'];
  const previous = new Map(globals.map((name) => [name, Object.getOwnPropertyDescriptor(globalThis, name)]));
  for (const name of globals)
    Object.defineProperty(globalThis, name, {
      configurable: true,
      value: name === 'IS_REACT_ACT_ENVIRONMENT' ? true : dom.window[name],
    });
  const originalFetch = globalThis.fetch;
  const calls = [];
  globalThis.fetch = async (path, options = {}) => {
    calls.push({ path, method: options.method ?? 'GET' });
    assert.equal(options.method ?? 'GET', 'GET', 'log visualization cannot execute factory work');
    const match = path.match(/^\/api\/v1\/factory\/recordings\/([^/]+)\/artifacts\/([^/]+)$/);
    assert.ok(match, `read-only recorded artifact URL: ${path}`);
    assert.equal(decodeURIComponent(match[1]), run.id);
    const artifact = run.artifacts.find((value) => value.id === decodeURIComponent(match[2]));
    assert.ok(artifact);
    return new Response(await artifactText(artifact));
  };
  const root = createRoot(dom.window.document.getElementById('root'));
  const find = (name) => dom.window.document.querySelector(`[data-testid="workflow-demo-${name}"]`);
  const all = (name) => [...dom.window.document.querySelectorAll(`[data-testid="workflow-demo-${name}"]`)];
  const render = async (cursor, options = {}) => {
    const projected = projectReplay(run, events, cursor);
    await act(async () => {
      root.render(
        React.createElement(ExecutionLog, {
          run: projected,
          events: events.slice(0, cursor),
          recordingId: run.id,
          ...options,
        }),
      );
    });
    return projected;
  };
  const click = async (element) => {
    assert.ok(element, 'recorded command control exists');
    await act(async () => {
      element.dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true, cancelable: true }));
      for (let index = 0; index < 8; index += 1) await new Promise((resolve) => setImmediate(resolve));
    });
  };
  try {
    await callback({ dom, find, all, render, click, calls });
  } finally {
    await act(async () => root.unmount());
    globalThis.fetch = originalFetch;
    for (const [name, descriptor] of previous) {
      if (descriptor) Object.defineProperty(globalThis, name, descriptor);
      else delete globalThis[name];
    }
    dom.window.close();
  }
}

test('real command PID, output and raw download identities appear only at their observed event prefix', async () => {
  await withLog(async ({ dom, all, find, render }) => {
    await render(4);
    assert.equal(all('log-command').length, 0);
    await render(5);
    assert.equal(all('log-command').length, 1);
    assert.doesNotMatch(dom.window.document.body.textContent, /38756/);
    assert.equal(all('log-download').length, 0);
    await render(6);
    assert.equal(find('log-stderr').textContent, events[5].payload.text);
    await render(7);
    const command = events[6].payload.command;
    assert.equal(command.pid, 38756);
    assert.equal(find('log-pid').textContent, String(command.pid));
    assert.equal(find('log-stderr').textContent, command.stderr, 'finished metadata cannot duplicate streamed output');
    const links = all('log-download');
    assert.equal(links.length, 2);
    for (const stream of ['stdout', 'stderr']) {
      const artifact = run.artifacts.find(
        (item) =>
          item.producer === 'n1' && item.path === command[`${stream}_path`] && item.kind === `process.${stream}`,
      );
      assert.ok(artifact);
      const link = links.find((element) => element.getAttribute('data-variant') === stream);
      assert.ok(link, `${stream} is a published raw artifact`);
      assert.equal(link.getAttribute('href'), `/api/v1/factory/recordings/${run.id}/artifacts/${artifact.id}`);
      assert.equal(link.getAttribute('data-sha256'), artifact.sha256);
      assert.equal(link.getAttribute('data-artifact-id'), artifact.id);
    }
    await render(5);
    assert.equal(all('log-download').length, 0, 'rewind removes future raw-file access');
    assert.doesNotMatch(dom.window.document.body.textContent, /38756/);
  });
});

test('complete archived command list retains real attempts and exact untruncated command streams', async () => {
  await withLog(async ({ dom, all, find, render, click, calls }) => {
    const projected = await render(events.length);
    const expected = projected.nodes.flatMap((node) =>
      node.attempts.flatMap((attempt) =>
        attempt.commands.map((command, index) => ({
          node,
          attempt,
          command,
          key: `${node.id}/${attempt.number}/${index + 1}`,
        })),
      ),
    );
    assert.equal(expected.length, 20);
    assert.equal(all('log-command').length, expected.length);
    assert.deepEqual(
      all('log-group')
        .map((element) => element.getAttribute('data-variant'))
        .sort(),
      [...new Set(expected.map(({ node, attempt }) => `${node.id}/${attempt.number}`))].sort(),
      'commands remain grouped by their actual node and attempt identities',
    );
    for (const { node, attempt, command, key } of expected) {
      const item = all('log-command').find((element) => element.getAttribute('data-variant') === key);
      await click(item);
      assert.equal(find('log-stdout').textContent, command.stdout ?? '', `${key} stdout is exact`);
      assert.equal(find('log-stderr').textContent, command.stderr ?? '', `${key} stderr is exact`);
      assert.equal(
        find('log-pid').textContent,
        command.pid === undefined ? 'Not recorded at this event' : String(command.pid),
      );
      assert.equal(find('log-cwd').textContent, command.cwd);
      assert.deepEqual(JSON.parse(find('log-argv').textContent), command.argv);
      assert.equal(find('log-start').textContent, command.started_at ?? 'Not recorded');
      assert.equal(find('log-finish').textContent, command.finished_at ?? 'Not recorded at this event');
      assert.equal(
        find('log-exit').textContent,
        command.exit_code == null ? 'Not recorded at this event' : String(command.exit_code),
      );
      assert.equal(
        find('log-duration').textContent,
        command.duration_s === undefined ? 'Not recorded at this event' : `${command.duration_s} s`,
      );
      assert.ok(dom.window.document.body.textContent.includes(node.name));
      assert.ok(attempt.number >= 1);
    }
    const longest = expected.reduce((best, item) =>
      (item.command.stdout?.length ?? 0) > (best.command.stdout?.length ?? 0) ? item : best,
    );
    await click(all('log-command').find((element) => element.getAttribute('data-variant') === longest.key));
    const artifact = projected.artifacts.find(
      (item) => item.producer === longest.node.id && item.path === longest.command.stdout_path,
    );
    const fullText = await artifactText(artifact);
    assert.ok(fullText.length > 8000, 'actual production extractor output spans more than a two-line preview');
    assert.equal(find('log-stdout').textContent, fullText);
    const createObjectURL = URL.createObjectURL;
    const anchorClick = dom.window.HTMLAnchorElement.prototype.click;
    let downloaded;
    let filename;
    URL.createObjectURL = (blob) => {
      downloaded = blob;
      return createObjectURL(blob);
    };
    dom.window.HTMLAnchorElement.prototype.click = function () {
      filename = this.download;
    };
    try {
      await click(all('log-download').find((element) => element.getAttribute('data-variant') === 'stdout'));
      assert.ok(downloaded, 'published raw log is fetched for the download');
      assert.equal(await downloaded.text(), fullText, 'download retains every recorded output byte');
      assert.equal(filename, artifact.path.split('/').at(-1));
      assert.equal(calls.at(-1).path, `/api/v1/factory/recordings/${run.id}/artifacts/${artifact.id}`);
    } finally {
      URL.createObjectURL = createObjectURL;
      dom.window.HTMLAnchorElement.prototype.click = anchorClick;
    }
    assert.ok(calls.every((call) => call.method === 'GET'));
  });
});

test('execution log has no frontend clock, synthetic command creation or clipped stream rendering', async () => {
  const source = await readFile(new URL('../src/features/workflowDemo/ExecutionLog.tsx', import.meta.url), 'utf8');
  assert.doesNotMatch(source, /setTimeout|setInterval|requestAnimationFrame|performance\.now|Date\.now/);
  assert.doesNotMatch(source, /factoryClient\.(?:start|replay|stream)\s*\(/);
  assert.doesNotMatch(source, /(?:stdout|stderr)\??\.slice\s*\(/);
});

const ascendArchive = await JSZip.loadAsync(
  await readFile(
    new URL('../../../../../docs/code/Missions/software-factory/recordings/ascend-inner-stages.zip', import.meta.url),
  ),
);
const ascendManifest = JSON.parse(await ascendArchive.file('manifest.json').async('string'));
const ascendRun = JSON.parse(await ascendArchive.file('blobs/' + ascendManifest.provenance.run_sha256).async('string'));
const ascendEvents = (await ascendArchive.file('blobs/' + ascendManifest.provenance.events_sha256).async('string'))
  .trim()
  .split('\n')
  .map((line) => JSON.parse(line));
const activityTypes = new Set([
  'stage.started',
  'stage.verified',
  'stage.failed',
  'stage.blocked',
  'workflow.expanded',
  'implementation.selected',
]);

test('recorded Ascend factory worker PID remains distinct from command subprocess metadata', async () => {
  await withLog(async ({ find, render }) => {
    assert.equal(ascendRun.executor.pid, 24787);
    const projected = projectReplay(ascendRun, ascendEvents, 31);
    await render(0, { run: projected, events: ascendEvents.slice(0, 31), recordingId: ascendRun.id });
    assert.equal(find('log-worker-pid').textContent, String(ascendRun.executor.pid));
    assert.notEqual(find('log-pid').textContent, String(ascendRun.executor.pid));

    // Older transport shapes may omit this optional metadata. Omission must
    // remain explicit; this structural check does not rewrite a real archive.
    const { executor: _executor, ...withoutWorkerMetadata } = projected;
    await render(0, { run: withoutWorkerMetadata, events: ascendEvents.slice(0, 31), recordingId: ascendRun.id });
    assert.match(find('log-worker-pid').textContent, /not recorded/i);
  });
});

test('Ascend stage activity follows every original prefix, including stages with no subprocess commands', async () => {
  await withLog(async ({ all, find, render }) => {
    for (const cursor of [31, 64, 72, ascendEvents.length]) {
      const prefix = ascendEvents.slice(0, cursor);
      const projected = projectReplay(ascendRun, ascendEvents, cursor);
      await render(0, { run: projected, events: prefix, recordingId: ascendRun.id });
      assert.ok(find('log-stage-activity'));
      const expected = prefix.filter((event) => activityTypes.has(event.type));
      const items = all('log-activity-item');
      assert.deepEqual(
        items.map((item) => Number(item.getAttribute('data-variant'))),
        expected.map((event) => event.sequence),
        `event ${cursor} displays the entire actual activity prefix in original order`,
      );
      for (const [index, event] of expected.entries()) {
        const item = items[index];
        assert.equal(item.getAttribute('data-event-type'), event.type);
        if (event.node_id) assert.equal(item.getAttribute('data-node'), event.node_id);
        assert.equal(item.querySelector('[data-testid="workflow-demo-log-activity-time"]').textContent, event.time);
        if (event.type === 'stage.started') {
          assert.ok(item.textContent.includes(event.payload.stage.name));
          assert.ok(item.textContent.includes(event.payload.stage.entrypoint));
        }
        const node = projected.nodes.find((value) => value.id === event.node_id);
        const recordedRef =
          event.type === 'workflow.expanded'
            ? event.payload.path
            : event.type === 'implementation.selected'
              ? event.payload.selected_ref
              : node?.workflow_path;
        if (recordedRef)
          assert.equal(item.querySelector('[data-testid="workflow-demo-log-activity-ref"]').textContent, recordedRef);
        assert.deepEqual(
          [...item.querySelectorAll('[data-testid="workflow-demo-log-activity-output"]')].map((output) =>
            output.getAttribute('data-variant'),
          ),
          (event.payload.outputs ?? []).map((artifact) => artifact.id),
          `${event.sequence} exposes only its actually published output identities`,
        );
      }
      assert.deepEqual(
        all('log-activity-output').map((output) => output.getAttribute('data-variant')),
        expected.flatMap((event) => (event.payload.outputs ?? []).map((artifact) => artifact.id)),
      );
      if (cursor === 31) {
        assert.equal(items.filter((item) => /^n(?:9|10|11|12|13|14)$/.test(item.getAttribute('data-node'))).length, 0);
        assert.equal(
          items.some((item) => item.getAttribute('data-node') === 'n7'),
          false,
        );
      }
      if (cursor === 64) {
        const codegen = projected.nodes.find((node) => node.id === 'n7');
        assert.equal(codegen.attempts.flatMap((attempt) => attempt.commands).length, 0);
        assert.deepEqual(
          items
            .filter((item) => item.getAttribute('data-node') === 'n7')
            .map((item) => item.getAttribute('data-event-type')),
          ['stage.started'],
        );
      }
      if (cursor === 72) {
        for (const nodeId of ['n9', 'n10', 'n11', 'n12', 'n13', 'n14']) {
          const node = projected.nodes.find((value) => value.id === nodeId);
          assert.equal(node.attempts.flatMap((attempt) => attempt.commands).length, 0);
          assert.deepEqual(
            items
              .filter((item) => item.getAttribute('data-node') === nodeId)
              .map((item) => item.getAttribute('data-event-type')),
            ['stage.started', 'stage.verified'],
            `${nodeId} remains visible through its real stage lifecycle without inventing child processes`,
          );
        }
        assert.deepEqual(
          items
            .filter((item) => item.getAttribute('data-node') === 'n7')
            .map((item) => item.getAttribute('data-event-type')),
          ['stage.started', 'stage.verified'],
        );
      }
    }
  });
});
