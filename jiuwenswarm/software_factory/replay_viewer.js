/* Historical playback only. State is projected from the recorded event prefix.
 * This module has no execution API, network requests, or synthetic events.
 * The exporter concatenates the unchanged shared projector before this file.
 */
const recording = REPLAY_RECORDING;
const replayEvents = normalizeReplayEvents(recording.events);
const el = (id) => document.getElementById(id);
const controls = { play: el('play'), previous: el('previous'), next: el('next'), seek: el('seek'), speed: el('speed') };
let cursor = 0;
let selectedNode = null;
let followExecution = true;
let activeTab = 'Terminal';
let playing = false;
let frame = null;
let clockStart = 0;
let clockOffset = 0;
let projected;

function make(tag, text, className) {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = String(text);
  if (className) node.className = className;
  return node;
}

function dot(status) {
  const node = make('span', undefined, `dot ${status || 'pending'}`);
  node.setAttribute('aria-label', status || 'pending');
  return node;
}

function utc(time) {
  return time ? new Date(time).toISOString().replace('T', ' ').replace('Z', ' UTC') : '';
}

function download(base64, filename, mime = 'application/octet-stream') {
  const bytes = Uint8Array.from(atob(base64), (character) => character.charCodeAt(0));
  const url = URL.createObjectURL(new Blob([bytes], { type: mime }));
  const link = make('a');
  link.href = url;
  link.download = filename;
  document.body.append(link);
  link.click();
  link.remove();
  // Retain the object URL until page unload: browsers can consume downloads
  // asynchronously, and no timer is needed for recorded playback.
}

function publishedAttachments() {
  const visible = new Set(projected.artifacts.map((artifact) => artifact.id));
  return Object.values(recording.attachments).filter((entry) => entry.sequence <= cursor && visible.has(entry.artifact.id));
}

function selected() {
  return projected.nodes.find((node) => node.id === selectedNode);
}

function edgeState(edge) {
  return replayEdgeStatus(edge, projected);
}

function renderPool() {
  const container = el('pool');
  container.replaceChildren();
  const groups = new Map();
  for (const stage of recording.catalog) {
    if (!groups.has(stage.workflow_id)) groups.set(stage.workflow_id, []);
    groups.get(stage.workflow_id).push(stage);
  }
  for (const [workflow, stages] of groups) {
    container.append(make('div', workflow.replaceAll('_', ' '), 'pool-group'));
    for (const stage of stages) {
      const nodes = projected.nodes.filter((node) => node.stage_id === stage.id);
      const button = make('button', stage.name, `pool-item${nodes.length ? ' selected' : ''}`);
      button.onclick = () => {
        if (nodes.length) {
          followExecution = false;
          selectedNode = nodes.at(-1).id;
          render();
        }
      };
      container.append(button);
    }
  }
}

function svgNode(tag, attributes) {
  const node = document.createElementNS('http://www.w3.org/2000/svg', tag);
  for (const [key, value] of Object.entries(attributes)) node.setAttribute(key, String(value));
  return node;
}

function renderGraph() {
  const graph = el('graph');
  graph.replaceChildren();
  // Place extracted stages before their actual consumers even when the stages
  // were admitted after the first graph revision. Ordering changes no edges.
  const pending = new Map(projected.nodes.map((node) => [node.id, node]));
  const nodes = [];
  while (pending.size) {
    const next = [...pending.values()].find((node) => !projected.edges.some((edge) =>
      edge.to === node.id && pending.has(edge.from)));
    if (!next) { nodes.push(...pending.values()); break; }
    nodes.push(next);
    pending.delete(next.id);
  }
  const width = Math.max(560, graph.parentElement.clientWidth - 24);
  const columns = Math.max(2, Math.floor(width / 205));
  const gap = width / columns;
  const positions = new Map(nodes.map((node, index) => {
    const row = Math.floor(index / columns);
    const col = row % 2 ? columns - 1 - index % columns : index % columns;
    return [node.id, { x: col * gap + (gap - 172) / 2, y: row * 116 + 20 }];
  }));
  const height = Math.max(graph.parentElement.clientHeight - 24, Math.ceil(nodes.length / columns) * 116 + 20);
  graph.style.width = `${width}px`;
  graph.style.height = `${height}px`;
  const svg = svgNode('svg', { viewBox: `0 0 ${width} ${height}`, 'aria-hidden': 'true' });
  const defs = svgNode('defs', {});
  for (const status of ['pending', 'running', 'verified', 'failed', 'blocked']) {
    const marker = svgNode('marker', { id: `arrow-${status}`, viewBox: '0 0 6 6', refX: 5, refY: 3, markerWidth: 5, markerHeight: 5, orient: 'auto' });
    const path = svgNode('path', { d: 'M 0 0 L 6 3 L 0 6 z' });
    path.style.fill = `var(--${status === 'verified' ? 'color-feedback-success' : status === 'running' ? 'color-feedback-info' : ['failed', 'blocked'].includes(status) ? 'color-feedback-danger' : 'color-border-strong'})`;
    marker.append(path);
    defs.append(marker);
  }
  svg.append(defs);
  projected.edges.forEach((edge, index) => {
    const from = positions.get(edge.from);
    const to = positions.get(edge.to);
    if (!from || !to) return;
    const sameRow = from.y === to.y;
    const forward = to.x > from.x;
    const x1 = sameRow ? from.x + (forward ? 172 : 0) : from.x + 86;
    const y1 = from.y + (sameRow ? 28 : 56);
    const x2 = sameRow ? to.x + (forward ? 0 : 172) : to.x + 86;
    const y2 = to.y + (sameRow ? 28 : 0);
    const offset = 14 + (index % 3) * 9;
    const bend = sameRow ? y1 - offset : (y1 + y2) / 2 + offset;
    const d = sameRow ? `M ${x1} ${y1} C ${(x1 + x2) / 2} ${bend}, ${(x1 + x2) / 2} ${bend}, ${x2} ${y2}`
      : `M ${x1} ${y1} C ${x1} ${bend}, ${x2} ${bend}, ${x2} ${y2}`;
    const status = edgeState(edge);
    svg.append(svgNode('path', { d, class: `edge ${status}`, 'marker-end': `url(#arrow-${status})` }));
    const label = svgNode('text', { x: (x1 + x2) / 2, y: sameRow ? bend - 3 : bend - 2, class: 'edge-label', 'text-anchor': 'middle' });
    label.textContent = edge.data;
    svg.append(label);
  });
  graph.append(svg);
  for (const node of nodes) {
    const position = positions.get(node.id);
    const button = make('button', undefined, `node${selectedNode === node.id ? ' selected' : ''}`);
    button.style.left = `${position.x}px`;
    button.style.top = `${position.y}px`;
    button.append(dot(node.status), make('span', node.name, 'node-label'));
    button.setAttribute('aria-label', `${node.name}: ${node.status}`);
    button.onclick = () => { followExecution = false; selectedNode = node.id; render(); };
    graph.append(button);
  }
  const revision = projected.graph_revisions.at(-1)?.revision;
  el('graph-title').textContent = revision ? `Production Graph · ${revision}` : 'Production Graph';
}

function textBlock(container, value, className) {
  if (value !== undefined && value !== null && value !== '') container.append(make('pre', typeof value === 'string' ? value : JSON.stringify(value, null, 2), className));
}

function renderTerminal(container) {
  const node = selected();
  const list = node ? [node] : projected.nodes;
  for (const item of list) {
    for (const attempt of item.attempts || []) {
      const section = make('section', undefined, 'attempt');
      const heading = make('div', undefined, 'attempt-head');
      heading.append(dot(attempt.status), make('strong', `${node ? '' : `${item.name} · `}Attempt ${attempt.number}`));
      section.append(heading);
      for (const command of attempt.commands || []) {
        const row = make('div', undefined, 'command');
        textBlock(row, `$ ${(command.argv || []).join(' ')}`, 'argv');
        textBlock(row, command.stdout);
        textBlock(row, command.stderr);
        if (command.exit_code !== undefined && command.exit_code !== null) textBlock(row, `Exit ${command.exit_code}`);
        section.append(row);
      }
      textBlock(section, attempt.error);
      container.append(section);
    }
  }
}

function renderCodeDiff(container) {
  const attachments = publishedAttachments().filter((entry) => entry.artifact.kind === 'construction.code_diff');
  for (const entry of attachments) {
    for (const file of entry.diff.files) {
      const pair = make('div', undefined, 'code-pair');
      for (const [path, content, className] of [[file.source_path, file.source_code, 'original'], [file.generated_path, file.generated_code, 'generated']]) {
        const section = make('section');
        section.append(make('h3', path));
        textBlock(section, content, className);
        pair.append(section);
      }
      container.append(pair);
    }
  }
}

function artifactButton(entry) {
  const name = entry.artifact.path.split(/[\\/]/).at(-1);
  const button = make('button', `Download ${name}`, 'file-control');
  button.onclick = () => download(entry.base64, name);
  return button;
}

function renderSource(container) {
  for (const entry of publishedAttachments()) {
    container.append(artifactButton(entry));
    if (['construction.cpp', 'construction.header', 'construction.cmake', 'value.report'].includes(entry.artifact.kind)) textBlock(container, entry.text);
  }
}

function renderEvents(container) {
  replayEvents.slice(0, cursor).forEach((event, index) => {
    if (event.type === 'command.output') return;
    const row = make('div', undefined, 'event-row');
    const button = make('button', `${event.sequence} · ${utc(event.time)}\n${event.type}${event.node_id ? ` · ${event.node_id}` : ''}`);
    button.onclick = () => { pause(); cursor = index + 1; followExecution = false; selectedNode = event.node_id || selectedNode; render(); };
    row.append(button);
    if (event.type === 'graph.updated') textBlock(row, event.payload.reason);
    if (event.type === 'stage.failed' || event.type === 'stage.blocked') textBlock(row, event.payload.error);
    container.append(row);
  });
}

function renderInputs(container) {
  const node = selected();
  for (const attempt of node?.attempts || []) {
    container.append(make('strong', `Attempt ${attempt.number}`));
    textBlock(container, attempt.inputs || []);
    textBlock(container, attempt.outputs || []);
    textBlock(container, attempt.verification);
  }
}

function renderProvenance(container) {
  for (const [key, value] of Object.entries(recording.provenance)) {
    if (key === 'source_files') continue;
    const row = make('div', undefined, 'provenance-row');
    row.append(make('strong', key));
    textBlock(row, value);
    container.append(row);
  }
  for (const [name, base64] of Object.entries(recording.raw_evidence)) {
    const button = make('button', `Download ${name}`, 'file-control');
    button.disabled = cursor < replayEvents.length;
    button.onclick = () => download(base64, name);
    container.append(button);
  }
  for (const license of recording.licenses || []) {
    if (license.sequence > cursor) continue;
    container.append(make('strong', `${license.repository_url} · ${license.commit_sha}`));
    textBlock(container, license.text);
    const button = make('button', 'Download STRATA LICENSE', 'file-control');
    button.onclick = () => download(license.base64, 'STRATA-LICENSE');
    container.append(button);
  }
}

function renderDetail() {
  const tabs = el('tabs');
  tabs.replaceChildren();
  const codeAvailable = publishedAttachments().some((entry) => entry.artifact.kind === 'construction.code_diff');
  const sourceAvailable = publishedAttachments().length > 0;
  for (const name of ['Terminal', 'Code Diff', 'Source', 'Inputs', 'Events', 'Provenance']) {
    const button = make('button', name, name === activeTab ? 'active' : '');
    button.disabled = (name === 'Code Diff' && !codeAvailable) || (name === 'Source' && !sourceAvailable);
    button.onclick = () => { activeTab = name; el('detail').scrollTop = 0; renderDetail(); };
    tabs.append(button);
  }
  const heading = el('detail-heading');
  heading.replaceChildren();
  const node = selected();
  if (node) heading.append(dot(node.status), make('span', node.name));
  const container = el('detail');
  const scrollTop = container.scrollTop;
  container.replaceChildren();
  const renderers = { Terminal: renderTerminal, 'Code Diff': renderCodeDiff, Source: renderSource, Inputs: renderInputs, Events: renderEvents, Provenance: renderProvenance };
  renderers[activeTab](container);
  container.scrollTop = scrollTop;
}

function render() {
  projected = projectReplay(recording.run, replayEvents, cursor);
  if (selectedNode && !projected.nodes.some((node) => node.id === selectedNode)) selectedNode = null;
  if (!selectedNode || followExecution) {
    const current = replayEvents.slice(0, cursor).findLast((event) => event.node_id);
    selectedNode = current?.node_id || projected.nodes[0]?.id || null;
  }
  controls.seek.value = String(cursor);
  controls.previous.disabled = cursor === 0;
  controls.next.disabled = cursor === replayEvents.length;
  el('position').textContent = `${cursor} / ${replayEvents.length}`;
  el('run-id').textContent = recording.run.id;
  el('record-time').textContent = utc(projected.replay.time);
  const status = el('run-status');
  status.replaceChildren(dot(projected.status), make('span', projected.status));
  renderPool();
  renderGraph();
  renderDetail();
}

function pause() {
  playing = false;
  if (frame !== null) cancelAnimationFrame(frame);
  frame = null;
  controls.play.textContent = 'Play';
}

function tick(now) {
  if (!playing) return;
  const elapsed = clockOffset + (now - clockStart) * Number(controls.speed.value);
  let nextCursor = cursor;
  while (nextCursor < replayEvents.length && eventOffset(replayEvents, nextCursor) <= elapsed) nextCursor += 1;
  if (nextCursor !== cursor) { cursor = nextCursor; render(); }
  if (cursor >= replayEvents.length) pause();
  else frame = requestAnimationFrame(tick);
}

controls.play.onclick = () => {
  if (playing) { pause(); return; }
  if (cursor >= replayEvents.length) cursor = 0;
  followExecution = true;
  clockOffset = cursor ? eventOffset(replayEvents, cursor - 1) : 0;
  clockStart = performance.now();
  playing = true;
  controls.play.textContent = 'Pause';
  frame = requestAnimationFrame(tick);
};
controls.previous.onclick = () => { pause(); followExecution = true; cursor = Math.max(0, cursor - 1); render(); };
controls.next.onclick = () => { pause(); followExecution = true; cursor = Math.min(replayEvents.length, cursor + 1); render(); };
controls.seek.max = String(replayEvents.length);
controls.seek.oninput = () => { pause(); followExecution = true; cursor = Number(controls.seek.value); render(); };
controls.speed.onchange = () => {
  if (!playing) return;
  clockOffset = cursor ? eventOffset(replayEvents, cursor - 1) : 0;
  clockStart = performance.now();
};
window.addEventListener('resize', renderGraph);
window.addEventListener('beforeunload', pause);
render();
