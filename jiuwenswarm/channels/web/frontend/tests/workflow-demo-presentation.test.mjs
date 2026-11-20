import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import JSZip from 'jszip';
import { JSDOM } from 'jsdom';
import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { Simulate } from 'react-dom/test-utils';
import { projectReplay } from '../src/features/workflowDemo/replayProjection.js';
import { WorkflowDemo } from '../node_modules/.cache/factory-ui/WorkflowDemo.js';
import {
  catalogFromStages,
  compositionCounts,
  nextRecordedCursor,
  nodeOperationIdentity,
  productionPath,
  replayCheckpoints,
  nodePoolRef,
  recordingTitle,
  requestScope,
} from '../node_modules/.cache/factory-ui/presentationModel.js';

async function loadRecording(name) {
  const archive = await JSZip.loadAsync(
    await readFile(
      new URL(`../../../../../docs/code/Missions/software-factory/recordings/${name}.zip`, import.meta.url),
    ),
  );
  const manifest = JSON.parse(await archive.file('manifest.json').async('string'));
  const bySuffix = async (suffix) => {
    const entry = Object.entries(manifest.path_map).find(([path]) => path.endsWith(suffix));
    assert.ok(entry, `recording contains ${suffix}`);
    return archive.file(entry[1].blob).async('string');
  };
  const run = JSON.parse(await archive.file('blobs/' + manifest.provenance.run_sha256).async('string'));
  const events = (await archive.file('blobs/' + manifest.provenance.events_sha256).async('string'))
    .trim()
    .split('\n')
    .map((line) => JSON.parse(line));
  const catalog = JSON.parse(await bySuffix('/recipe/catalog.json'));
  const artifact = async (id) => {
    const item = run.artifacts.find((value) => value.id === id);
    assert.ok(item, `published artifact ${id}`);
    return archive.file(manifest.path_map[item.path].blob).async('uint8array');
  };
  return {
    schema: 'ai4r.recording-view:1',
    run,
    events,
    catalog,
    workflow_catalog: run.workflow_catalog ?? null,
    read_only: true,
    provenance: manifest.provenance,
    artifact,
  };
}

const core = await loadRecording('core');
const mixed = await loadRecording('mixed');
const native = await loadRecording('ascend-inner-stages');

function summary(value) {
  return {
    id: value.run.id,
    status: value.run.status,
    request: value.run.request,
    created_at: value.run.created_at,
    updated_at: value.run.updated_at,
    event_count: value.events.length,
    graph_revision_count: value.run.graph_revisions.length,
    artifact_count: value.run.artifacts.length,
    read_only: true,
  };
}

test('real recorded task differences preserve scope, hierarchy custody and actual lowering instances', () => {
  assert.equal(core.run.request.target_backend, 'cpu');
  assert.equal(mixed.run.request.target_backend, 'cpu');
  assert.equal(core.run.request.task.acceptance.native_execution === true, false);
  assert.equal(mixed.run.request.task.acceptance.full_model_inference === true, false);
  assert.deepEqual(compositionCounts(core.run.nodes), {
    stages: 19,
    workflows: 11,
    subworkflows: 16,
    implementations: 3,
  });
  assert.equal(compositionCounts(mixed.run.nodes).implementations, 2);
  assert.notDeepEqual(core.run.request.task.source_scope, mixed.run.request.task.source_scope);
  assert.ok(!requestScope(core.run.request).includes('native execution'));
  const stage = core.catalog[0];
  const flat = [stage, { ...stage, id: 'other.stage', workflow_id: 'other-workflow' }];
  const catalog = catalogFromStages(flat);
  assert.equal(catalog.groups.length, 2);
  assert.equal(catalog.subworkflows.length, 2);
  assert.deepEqual(catalog.subworkflows[0].stages, [stage]);
  const checkpoints = replayCheckpoints(core.events);
  assert.equal(checkpoints[0].kind, 'source.checkout');
  assert.equal(new Set(checkpoints.map((checkpoint) => checkpoint.sequence)).size, checkpoints.length);
  for (const checkpoint of checkpoints) {
    const event = core.events[checkpoint.cursor - 1];
    assert.equal(checkpoint.sequence, event.sequence);
    assert.ok(
      event.type.startsWith('run.') || event.payload.outputs.some((artifact) => artifact.kind === checkpoint.kind),
    );
  }
  const path = productionPath(core.run);
  assert.equal(path.nodes[path.nodes.length - 1].stage_id, 'construction.package');
  for (let index = 1; index < path.nodes.length; index += 1)
    assert.ok(
      core.run.edges.some((edge) => edge.from === path.nodes[index - 1].id && edge.to === path.nodes[index].id),
    );
  assert.deepEqual(productionPath({ ...core.run, artifacts: [] }).nodes, []);
  const lower = core.run.nodes.find((node) => node.stage_id === 'lower.cooperative');
  assert.equal(nodeOperationIdentity(lower, core.run), 'src/kernels/cuda/router_top10.cu:router_top10_kernel');
  assert.equal(
    nodeOperationIdentity(
      { ...lower, attempts: lower.attempts.map((attempt) => ({ ...attempt, inputs: [] })) },
      core.run,
    ),
    null,
  );
  assert.equal(nextRecordedCursor(core.events, 0, core.events[0]), 1);
  assert.throws(
    () => nextRecordedCursor(core.events, 0, { ...core.events[0], payload: { invented: true } }),
    /does not match/,
  );
  assert.throws(() => nextRecordedCursor(core.events, 0, mixed.events[0]), /does not match/);
});

test('recording viewer uses only read-only archive transport, exact source bytes and prefix publication', async () => {
  const dom = new JSDOM('<div id="root"></div>', {
    url: `http://localhost/?view=workflow&recording=${core.run.id}&replay=1`,
  });
  const names = [
    'window',
    'document',
    'navigator',
    'HTMLElement',
    'Event',
    'MouseEvent',
    'localStorage',
    'IS_REACT_ACT_ENVIRONMENT',
    'requestAnimationFrame',
    'cancelAnimationFrame',
  ];
  const previous = new Map(names.map((name) => [name, Object.getOwnPropertyDescriptor(globalThis, name)]));
  for (const name of names.slice(0, 8))
    Object.defineProperty(globalThis, name, {
      configurable: true,
      value: name === 'IS_REACT_ACT_ENVIRONMENT' ? true : dom.window[name],
    });
  Object.defineProperty(globalThis, 'requestAnimationFrame', { configurable: true, value: () => 1 });
  Object.defineProperty(globalThis, 'cancelAnimationFrame', { configurable: true, value: () => {} });
  const originalFetch = globalThis.fetch;
  const calls = [];
  const replaySessions = [];
  let delayListing = false;
  let resolveListing;
  const records = new Map([core, mixed, native].map((value) => [value.run.id, value]));
  globalThis.fetch = async (path, options = {}) => {
    calls.push({ path, method: options.method ?? 'GET' });
    assert.equal(options.method ?? 'GET', 'GET');
    if (path === '/api/v1/factory/catalog') return Response.json(catalogFromStages(core.catalog));
    if (path === '/api/v1/factory/recordings') {
      if (delayListing)
        return new Promise((resolve) => {
          resolveListing = resolve;
        });
      return Response.json({ recordings: [summary(core), summary(mixed), summary(native)] });
    }
    if (path.includes('/replay?')) {
      const query = new URL(path, 'http://localhost').searchParams;
      const after = Number(query.get('after'));
      const until = Number(query.get('until'));
      const checkpoint = replayCheckpoints(core.events).find((item) => item.sequence > after);
      assert.equal(until, checkpoint.sequence);
      assert.equal(query.get('speed'), '4');
      const session = { controller: null, aborted: false, closed: false };
      const body = new ReadableStream({
        start(controller) {
          session.controller = controller;
        },
      });
      options.signal.addEventListener('abort', () => {
        session.aborted = true;
        if (!session.closed) session.controller.error(new Error('Replay aborted'));
      });
      replaySessions.push(session);
      return new Response(body, { headers: { 'Content-Type': 'text/event-stream' } });
    }
    const match = path.match(/^\/api\/v1\/factory\/recordings\/([^/]+)(?:\/artifacts\/([^/]+))?$/);
    assert.ok(match, `read-only recording route: ${path}`);
    const value = records.get(decodeURIComponent(match[1]));
    assert.ok(value);
    if (match[2]) return new Response(await value.artifact(decodeURIComponent(match[2])));
    const { artifact: _, ...view } = value;
    return Response.json(view);
  };
  let root = createRoot(dom.window.document.getElementById('root'));
  const find = (id) => dom.window.document.querySelector(`[data-testid="workflow-demo-${id}"]`);
  const all = (id) => [...dom.window.document.querySelectorAll(`[data-testid="workflow-demo-${id}"]`)];
  const settle = async () => {
    for (let index = 0; index < 8; index += 1) await new Promise((resolve) => setImmediate(resolve));
  };
  const click = async (element) => {
    await act(async () => {
      element.dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true }));
    });
    await act(settle);
  };
  const change = async (element, value) => {
    await act(async () => {
      element.value = value;
      element.dispatchEvent(new dom.window.Event('change', { bubbles: true }));
    });
    await act(settle);
  };
  const tab = (id) => all('evidence-tab').find((item) => item.dataset.variant === id);
  try {
    await act(async () => {
      root.render(React.createElement(WorkflowDemo));
      await settle();
    });
    assert.equal(find('recorded-target').textContent, 'CPU');
    assert.equal(find('recorded-source-role').textContent, 'STRATA CUDA');
    assert.equal(find('recorded-cpu-role').textContent, 'CPU checks requested');
    assert.equal(find('recorded-reference-role'), null);
    assert.equal(find('task-form'), null);
    assert.equal(all('workflow-group').length, new Set(core.catalog.map((stage) => stage.workflow_id)).size);
    assert.equal(find('workflow-selector'), null);
    const poolOrder = all('workflow-group').map((group) => group.dataset.variant);
    assert.equal(dom.window.document.querySelectorAll('[data-testid="workflow-demo"] [title]').length, 0);
    assert.ok(all('pool-subworkflow-label').some((element) => element.textContent === 'Cooperative Lowering'));
    assert.equal(all('node').length, 0);
    assert.equal(calls.filter((value) => value.path.includes('/artifacts/')).length, 0);
    assert.equal(find('replay-speed').value, '4');
    await click(find('replay-play-pause'));
    assert.equal(find('replay-play-pause').getAttribute('aria-pressed'), 'true');
    assert.equal(all('node').length, 0);
    const firstGraph = core.events.findIndex((event) => event.type === 'graph.updated');
    await act(async () => {
      for (const event of core.events.slice(0, firstGraph + 1)) {
        replaySessions[0].controller.enqueue(
          new TextEncoder().encode(`event: recorded\ndata: ${JSON.stringify(event)}\n\n`),
        );
      }
      await settle();
    });
    const cursor = Number(find('replay-timeline').value);
    const prefix = projectReplay(core.run, core.events, cursor);
    assert.deepEqual(
      all('node').map((item) => item.dataset.variant),
      prefix.nodes.map((item) => item.id),
    );
    const beforeClockChange = all('node').map((item) => item.outerHTML);
    const originalNow = Date.now;
    Date.now = () => 4_102_444_800_000;
    try {
      await act(async () => {
        root.render(React.createElement(WorkflowDemo));
        await settle();
      });
      assert.equal(Number(find('replay-timeline').value), cursor);
      assert.deepEqual(
        all('node').map((item) => item.outerHTML),
        beforeClockChange,
      );
    } finally {
      Date.now = originalNow;
    }
    await click(find('replay-play-pause'));
    assert.equal(replaySessions[0].aborted, true);
    await act(async () => {
      Simulate.change(find('replay-timeline'), { target: { value: '0' } });
    });
    await click(find('replay-play-pause'));
    const firstCheckpoint = replayCheckpoints(core.events)[0];
    const boundedSession = replaySessions[replaySessions.length - 1];
    await act(async () => {
      for (const event of core.events.slice(0, firstCheckpoint.cursor))
        boundedSession.controller.enqueue(
          new TextEncoder().encode(`event: recorded\ndata: ${JSON.stringify(event)}\n\n`),
        );
      boundedSession.closed = true;
      boundedSession.controller.close();
      await settle();
    });
    assert.equal(find('replay-timeline').value, String(firstCheckpoint.cursor));
    assert.equal(find('replay-checkpoint').value, String(firstCheckpoint.cursor));
    assert.equal(find('replay-play-pause').getAttribute('aria-pressed'), 'false');
    assert.equal(find('error'), null);
    assert.equal(find('source-code'), null);
    await click(find('replay-play-pause'));
    const cppCheckpoint = replayCheckpoints(core.events).find((checkpoint) => checkpoint.kind === 'construction.cpp');
    await change(find('replay-checkpoint'), String(cppCheckpoint.cursor));
    assert.deepEqual(
      all('production-step').map((element) => element.dataset.variant),
      productionPath(projectReplay(core.run, core.events, cppCheckpoint.cursor)).nodes.map((node) => node.id),
    );
    assert.ok(find('composition-outputs').textContent.includes('strata_core.cpp'));
    assert.ok(!find('composition-outputs').textContent.includes('huawei_native_strata.zip'));
    assert.equal(all('internal-row').length, 3);
    assert.ok(
      find('internal-extraction').textContent.includes('Cooperative Implementation / Cooperative Lowering / Lower'),
    );
    for (const edge of all('internal-edge'))
      assert.ok(
        core.run.edges.some((recorded) => recorded.from === edge.dataset.from && recorded.to === edge.dataset.to),
      );
    await click(find('replay-result'));
    assert.deepEqual(
      all('workflow-group').map((group) => group.dataset.variant),
      poolOrder,
    );
    assert.equal(all('node').length, core.run.nodes.length);
    assert.match(find('composition-counts').textContent, /3 lowering instances/);
    const crossWorkflowEdges = core.run.edges.filter((edge) => {
      const from = core.run.nodes.find((node) => node.id === edge.from);
      const to = core.run.nodes.find((node) => node.id === edge.to);
      return (
        (nodePoolRef(from).split('/')[0] || from.workflow_id) !== (nodePoolRef(to).split('/')[0] || to.workflow_id)
      );
    });
    assert.equal(all('composition-handoff').length, crossWorkflowEdges.length);
    for (const handoff of all('composition-handoff')) {
      assert.ok(
        crossWorkflowEdges.some((edge) => edge.from === handoff.dataset.from && edge.to === handoff.dataset.to),
      );
      assert.ok(handoff.textContent.includes(' / '));
    }
    const buildNode = core.run.nodes.find((node) => node.stage_id === 'construction.build');
    const validationNode = core.run.nodes.find((node) => node.stage_id === 'construction.execute');
    const packageNode = core.run.nodes.find((node) => node.stage_id === 'construction.package');
    const buildValidation = all('composition-handoff').find(
      (row) => row.dataset.from === buildNode.id && row.dataset.to === validationNode.id,
    );
    const validationPackage = all('composition-handoff').find(
      (row) => row.dataset.from === validationNode.id && row.dataset.to === packageNode.id,
    );
    assert.ok(buildValidation.textContent.includes('Construction /'));
    assert.ok(buildValidation.textContent.includes('Verification /'));
    assert.ok(validationPackage.textContent.includes('Delivery /'));
    assert.equal(buildValidation.dataset.delivery, 'verified');
    assert.equal(validationPackage.dataset.delivery, 'verified');
    assert.equal(all('composition-selected-stage').length, core.run.nodes.length);
    const actualPath = productionPath(core.run).nodes;
    assert.deepEqual(
      all('production-step').map((element) => element.dataset.variant),
      actualPath.map((node) => node.id),
    );
    for (const edge of all('production-edge'))
      assert.ok(
        core.run.edges.some((recorded) => recorded.from === edge.dataset.from && recorded.to === edge.dataset.to),
      );
    assert.equal(find('replan-reason'), null);
    assert.equal(find('node-stage').textContent, 'construction.codegen');
    assert.ok(all('production-branch').some((element) => element.textContent.includes('swiglu_kernel')));
    assert.ok(all('production-branch').some((element) => element.textContent.includes('moe_combine_kernel')));

    await click(tab('diff'));
    const diffArtifact = core.run.artifacts.find((value) => value.kind === 'construction.code_diff');
    const diff = JSON.parse(new TextDecoder().decode(await core.artifact(diffArtifact.id)));
    assert.equal(all('code-diff-file').length, diff.files.length);
    assert.equal(all('code-diff-generated')[0].textContent, diff.files[0].generated_code);
    await click(tab('source'));
    const cpp = core.run.artifacts.find((value) => value.kind === 'construction.cpp');
    assert.equal(find('source-code').textContent, new TextDecoder().decode(await core.artifact(cpp.id)));
    await click(tab('build'));
    assert.match(find('cpu-evidence').textContent, /cpu_compilation_validatedtrue/);
    assert.match(find('native-evidence').textContent, /native_device_validatedfalse/);
    assert.match(find('native-evidence').textContent, /full_inference_validatedfalse/);
    await click(tab('downloads'));
    const zip = core.run.artifacts.find((value) => value.kind === 'construction.package');
    const download = all('artifact-download').find((value) => value.dataset.variant === zip.id);
    assert.ok(download.href.includes(`/recordings/${core.run.id}/artifacts/`));
    assert.equal(download.textContent, 'huawei_native_strata.zip');
    await act(async () => {
      Simulate.change(find('replay-timeline'), { target: { value: '0' } });
    });
    await act(settle);
    assert.equal(all('artifact-download').length, 0);
    assert.equal(all('node').length, 0);
    await click(find('replay-play-pause'));
    await change(find('recording-selector'), mixed.run.id);
    assert.equal(replaySessions[replaySessions.length - 1].aborted, true);
    assert.equal(all('node').length, 0);
    assert.equal(find('replay-timeline').value, '0');
    assert.equal(find('recorded-capabilities').textContent, mixed.run.request.task.capabilities.join(', '));
    await click(find('replay-result'));
    assert.equal(all('node').length, mixed.run.nodes.length);
    assert.match(find('composition-counts').textContent, /2 lowering instances/);
    await change(find('recording-selector'), native.run.id);
    await click(find('replay-result'));
    assert.equal(find('recorded-target').textContent, 'ASCEND');
    assert.equal(find('run-status').textContent, 'Source complete');
    assert.ok(find('recorded-acceptance').textContent.includes('Ascend source generation'));
    assert.ok(find('recorded-native-scope').textContent.includes('not requested'));
    assert.equal(recordingTitle(summary(native)), 'Ascend source + CPU reference');
    const nativePath = productionPath(native.run);
    assert.ok(['construction.native_sources', 'construction.cpu_validation'].includes(nativePath.endpoint.kind));
    await click(tab('composition'));
    assert.deepEqual(
      all('production-step').map((element) => element.dataset.variant),
      nativePath.nodes.map((node) => node.id),
    );
    assert.equal(native.workflow_catalog?.schema, 'factory.workflow.library.v1');
    if (native.workflow_catalog) {
      assert.equal(find('pool').dataset.librarySchema, 'factory.workflow.library.v1');
      const selectedRefs = new Set(native.run.nodes.map(nodePoolRef).filter(Boolean));
      for (const button of all('pool-card'))
        assert.equal(button.dataset.selection, selectedRefs.has(button.dataset.variant) ? 'selected' : 'idle');
      const skipped = all('pool-card').find(
        (button) => button.dataset.variant === 'scalar_implementation/scalar_lowering/extract',
      );
      assert.ok(skipped);
      assert.equal(skipped.dataset.selection, 'idle');
      const skippedDiscovery = all('pool-card').find(
        (button) => button.dataset.variant === 'function_extraction/function_extraction/discover',
      );
      assert.equal(skippedDiscovery.dataset.selection, 'idle');
      await click(skipped);
      assert.equal(find('inspected-pool-ref').textContent, 'scalar_implementation/scalar_lowering/extract');
      assert.equal(skipped.dataset.selection, 'idle');
    } else {
      assert.equal(find('pool').dataset.librarySchema, undefined);
      assert.equal(find('pool-title').textContent, 'Recorded stage declarations');
    }
    await click(tab('source'));
    const nativeCpp = native.run.artifacts.find((artifact) => artifact.kind === 'construction.native_cpp');
    const nativeBundle = native.run.artifacts.find((artifact) => artifact.kind === 'construction.native_sources');
    const nativeDiffArtifact = native.run.artifacts.find((artifact) => artifact.kind === 'construction.code_diff');
    const actualNativeDiff = JSON.parse(new TextDecoder().decode(await native.artifact(nativeDiffArtifact.id)));
    const firstMathPath = actualNativeDiff.files.find((file) => file.target === 'ASCEND').generated_path;
    let actualArchive;
    await act(async () => {
      actualArchive = await JSZip.loadAsync(await native.artifact(nativeBundle.id));
      await settle();
    });
    assert.equal(find('source-path').textContent, firstMathPath);
    assert.equal(find('source-code').dataset.entry, firstMathPath);
    assert.equal(find('source-code').textContent, await actualArchive.file(firstMathPath).async('string'));
    await change(find('source-file'), nativeCpp.id);
    assert.equal(find('source-code').textContent, new TextDecoder().decode(await native.artifact(nativeCpp.id)));
    assert.equal(find('source-path').textContent, 'src/strata_native.cpp');
    for (const path of ['src/ascend/router.cpp', 'src/ascend/swiglu.cpp', 'src/ascend/moe_combine.cpp']) {
      const option = all('source-file-option').find((element) => element.textContent.includes(path));
      assert.ok(option, path);
      await change(find('source-file'), option.value);
      assert.equal(find('source-code').dataset.entry, path);
      assert.equal(find('source-code').textContent, await actualArchive.file(path).async('string'));
      assert.ok(find('source-bundle-hash').textContent.includes(nativeBundle.sha256));
    }
    const runtimeHeader = all('source-file-option').find((element) =>
      element.textContent.includes('include/ascend_runtime.h'),
    );
    assert.ok(runtimeHeader);
    await change(find('source-file'), runtimeHeader.value);
    assert.equal(find('source-code').textContent, await actualArchive.file('include/ascend_runtime.h').async('string'));
    await click(tab('diff'));
    assert.equal(all('code-diff-generated-label')[0].textContent, 'Generated Ascend C++');
    assert.ok(all('code-diff-file')[0].dataset.variant.startsWith('src/ascend/'));
    await click(tab('build'));
    assert.ok(find('native-evidence').textContent.includes('NOT_RUN'));
    assert.ok(find('cpu-reference-summary').textContent.includes('352'));
    assert.ok(find('cpu-operation-results').textContent.includes('router_top10_kernel'));
    await click(find('new-task'));
    assert.equal(find('backend').value, 'ascend');
    const task = JSON.parse(find('engineering-task').value);
    assert.equal(task.acceptance.native_execution, true);
    assert.equal(task.acceptance.full_model_inference, true);
    assert.equal(task.acceptance.compare_original, true);
    assert.equal(
      calls.some((value) => /\/runs|\/stream/.test(value.path)),
      false,
    );
    await act(async () => root.unmount());
    dom.window.history.replaceState(null, '', '?view=workflow');
    delayListing = true;
    root = createRoot(dom.window.document.getElementById('root'));
    await act(async () => {
      root.render(React.createElement(WorkflowDemo));
      await settle();
    });
    await click(find('workspace-recording'));
    assert.equal(find('task-form'), null);
    assert.ok(find('opening-recordings').textContent.includes('Opening saved factory records'));
    await click(find('new-task'));
    await act(async () => {
      resolveListing(Response.json({ recordings: [summary(core), summary(mixed), summary(native)] }));
      await settle();
    });
    assert.ok(find('task-form'));
    assert.equal(find('recorded-input'), null);
    assert.equal(find('recording-selector').value, '');
  } finally {
    await act(async () => root.unmount());
    globalThis.fetch = originalFetch;
    dom.window.close();
    for (const [name, descriptor] of previous) {
      if (descriptor) Object.defineProperty(globalThis, name, descriptor);
      else delete globalThis[name];
    }
  }
});
