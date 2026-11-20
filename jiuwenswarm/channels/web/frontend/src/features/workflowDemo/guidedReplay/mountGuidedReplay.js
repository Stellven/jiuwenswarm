import './guided-replay.css';

// Local state is reset on each mount. The payload describes a recorded run and
// navigation only reveals its existing evidence.
export function mountGuidedReplay(container, data, initialPage = 'projects') {
  const DATA = data;
  const el = (tag, text, css) => {
    const node = container.ownerDocument.createElement(tag);
    if (text !== undefined) node.textContent = text;
    if (css) node.className = css;
    return node;
  };
  const button = (text, action, css, control, variant) => {
    const node = el('button', text, css);
    node.type = 'button';
    if (control) node.dataset.testid = 'workflow-demo-guided-' + control;
    if (variant !== undefined) node.dataset.variant = variant;
    node.addEventListener('click', action);
    return node;
  };
  const details = (title, text, control) => {
    const node = el('details');
    if (control) node.dataset.testid = 'workflow-demo-guided-' + control;
    node.append(el('summary', title), el('pre', text));
    return node;
  };
  const rows = new Map(DATA.graph.nodes.map((node) => [node.id, node]));
  const parts = new Map(
    DATA.workflows.flatMap((project) =>
      project.subworkflows.map((part) => [project.id + '.' + part.id, { project, part }]),
    ),
  );
  const buildActions = new Map(DATA.composition.build_actions.map((action) => [action.id, action]));
  const projects = DATA.workflows;
  const steps = [
    { id: 'projects', label: 'Projects' },
    { id: 'library', label: 'Build the Library' },
    { id: 'compose', label: 'Compose' },
    { id: 'scheduling', label: 'Scheduling' },
    { id: 'construction', label: 'Construction' },
    { id: 'product', label: 'Product' },
  ];
  const trace = DATA.events.filter((event) => event.type === 'node.verified');
  let state = steps.some((step) => step.id === initialPage) ? initialPage : 'projects';
  let position = 1;
  let replayStep = 0;
  let diagramObserver;
  let currentPart = '';
  const productTree = buildProductTree(Object.keys(DATA.files));
  let file = Object.hasOwn(DATA.files, 'src/ascend/router.cpp') ? 'src/ascend/router.cpp' : Object.keys(DATA.files)[0];
  const openProductFolders = new Set(
    file
      .split('/')
      .slice(0, -1)
      .map((_, index, segments) => segments.slice(0, index + 1).join('/') + '/'),
  );
  let productTreeScroll = 0;
  let compare = false;
  let catalogProject = 'strata';
  const openedGroups = new Set();
  const composeSteps = composeMilestones(DATA.composition.events);
  const composeFolders = new Set();
  let composeStep = 0;

  function renderProjects(view) {
    view.append(el('h2', 'Start with two open-source projects'));
    const grid = el('div', undefined, 'grid');
    for (const project of projects) {
      const box = el('article');
      const link = el('a', project.source.repository);
      link.href = project.source.repository;
      box.append(el('h3', project.name), link);
      grid.append(box);
    }
    view.append(
      grid,
      button('Open the Library', () => navigate('library'), 'primary', 'open-library'),
    );
  }

  function renderLibrary(view) {
    const project = DATA.catalog.find((project) => project.id === catalogProject);
    view.append(el('h2', 'Extract workflows from projects'));
    const controls = el('div', undefined, 'actions');
    for (const candidate of DATA.catalog) {
      const tab = button(
        candidate.name,
        () => {
          catalogProject = candidate.id;
          currentPart = '';
          render();
        },
        undefined,
        'project',
        candidate.id,
      );
      tab.setAttribute('aria-pressed', String(project.id === candidate.id));
      controls.append(tab);
    }
    view.append(controls, renderLibraryMethod(project));
    const layout = el('div', undefined, 'library-layout');
    const outline = el('article', undefined, 'library-outline');
    const allParts = project.groups.flatMap((group) => group.parts);
    const selected =
      allParts.find((part) => currentPart === project.id + '.' + part.id) ||
      allParts.find((part) => part.id === project.decomposition.part) ||
      allParts[0];
    for (const group of project.groups) {
      const section = el('details');
      const groupKey = project.id + '.' + group.id;
      section.open = openedGroups.has(groupKey) || group.parts.includes(selected);
      section.addEventListener('toggle', () => {
        if (section.open) openedGroups.add(groupKey);
        else openedGroups.delete(groupKey);
      });
      const title = el('summary', group.name);
      section.append(title);
      for (const part of group.parts) {
        const key = project.id + '.' + part.id;
        const selector = button(
          part.name,
          () => {
            currentPart = key;
            render();
          },
          undefined,
          'library-part',
          key,
        );
        selector.setAttribute('aria-pressed', String(part === selected));
        section.append(selector);
      }
      outline.append(section);
    }
    layout.append(outline, renderOriginalFunction(project, selected));
    view.append(layout);
    view.append(button('Choose parts for this task', () => navigate('compose'), 'primary', 'compose-task'));
  }

  function renderLibraryMethod(project) {
    const example = project.decomposition;
    const part = project.groups.flatMap((group) => group.parts).find((part) => part.id === example.part);
    const card = el('article', undefined, 'library-method');
    card.append(
      el('h3', part.name),
      el('p', 'A Python script extracts workflows where the original code hands off data.'),
    );

    const flow = el('div', undefined, 'extraction-flow');
    for (const [label, value, selected] of [
      ['Input', part.input, false],
      ['Extracted function', part.symbol, true],
      ['Output', part.output, false],
    ]) {
      if (flow.children.length) {
        const arrow = el('span', '→', 'extraction-arrow');
        arrow.setAttribute('aria-hidden', 'true');
        flow.append(arrow);
      }
      const step = el('div', undefined, selected ? 'extraction-function' : 'extraction-value');
      step.append(el('strong', label), el(selected ? 'code' : 'span', value));
      flow.append(step);
    }
    card.append(flow);

    const result = el('div', undefined, 'grid extraction-result');
    const extractor = el('section');
    extractor.append(el('h4', 'Python extractor'), el('pre', example.python));
    const entry = el('section', undefined, 'extraction-entry');
    entry.append(el('h4', 'Library entry'), el('p', project.name + ' / ' + example.group + ' / ' + part.name));
    const source = el('code', part.path + ':' + part.line + '–' + part.end_line);
    entry.append(source);
    if (example.registered && project.id === 'googletest') {
      entry.append(el('p', 'The adapter applies the name check to each candidate and returns the matches.'));
    }
    entry.append(
      button(
        'Open this entry',
        () => {
          currentPart = project.id + '.' + example.part;
          render();
          view.querySelector('.library-layout').scrollIntoView({ block: 'start' });
        },
        undefined,
        'open-extraction-entry',
      ),
    );
    result.append(extractor, entry);
    card.append(result);

    const proof = el('details');
    proof.dataset.testid = 'workflow-demo-guided-extraction-record';
    proof.append(
      el('summary', 'Original calls and extraction record'),
      el('p', 'The source map gives Python the function signature to find in the pinned source.'),
    );
    proof.append(el('pre', example.anchor));
    for (const call of example.calls) {
      const ref = el('a', call.path + ':' + call.line);
      ref.href = project.repository + '/blob/' + project.revision + '/' + call.path + '#L' + call.line;
      proof.append(ref, el('pre', call.code));
    }
    if (example.registered) {
      proof.append(
        details('Open the registered input and output contract', JSON.stringify(example.registered, null, 2)),
      );
    }
    card.append(proof);
    return card;
  }

  function renderOriginalFunction(project, part) {
    const panel = el('article');
    panel.append(el('h3', part.name));
    const properties = el('dl', undefined, 'function-contract');
    for (const [label, value] of [
      ['Receives', part.input],
      ['Produces', part.output],
      ['When used', part.when],
      ['Original function', part.symbol],
    ]) {
      if (value) properties.append(el('dt', label), el('dd', value));
    }
    panel.append(properties);
    const ref = el('a', part.path + ':' + part.line);
    ref.href = project.repository + '/blob/' + project.revision + '/' + part.path + '#L' + part.line;
    panel.append(ref, el('pre', part.code));
    if (part.recorded_part && DATA.graph.nodes.some((node) => node.id === project.id + '.' + part.recorded_part)) {
      const actions = el('div', undefined, 'actions');
      actions.append(
        button('Find this function in the build', () => navigate('compose'), undefined, 'locate-library-part'),
      );
      panel.append(actions);
    }
    return panel;
  }

  function drawPlan(canvas, cards, edges) {
    const bounds = canvas.getBoundingClientRect();
    const ratio = container.ownerDocument.defaultView.devicePixelRatio || 1;
    canvas.width = Math.ceil(bounds.width * ratio);
    canvas.height = Math.ceil(bounds.height * ratio);
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    ctx.scale(ratio, ratio);
    ctx.strokeStyle = ctx.fillStyle = getComputedStyle(canvas).color;
    ctx.lineWidth = 1.6;
    for (const edge of edges) {
      const from = cards.get(edge.from).getBoundingClientRect();
      const to = cards.get(edge.to).getBoundingClientRect();
      const across = from.right < to.left;
      const startX = (across ? from.right : (from.left + from.right) / 2) - bounds.left;
      const startY = (across ? (from.top + from.bottom) / 2 : from.bottom) - bounds.top;
      const endX = (across ? to.left : (to.left + to.right) / 2) - bounds.left;
      const endY = (across ? (to.top + to.bottom) / 2 : to.top) - bounds.top;
      const bendX = (startX + endX) / 2;
      ctx.beginPath();
      ctx.moveTo(startX, startY);
      if (across) {
        ctx.lineTo(bendX, startY);
        ctx.lineTo(bendX, endY);
      }
      ctx.lineTo(endX, endY);
      ctx.stroke();
      ctx.beginPath();
      ctx.moveTo(endX, endY);
      ctx.lineTo(endX - (across ? 7 : 4), endY - (across ? 4 : 7));
      ctx.lineTo(endX + (across ? -7 : 4), endY + (across ? 4 : -7));
      ctx.fill();
    }
  }

  function composeMilestones(events) {
    const selections = events
      .map((event, index) => ({ event, index }))
      .filter((entry) => entry.event.type === 'select')
      .map(({ event, index }) => {
        let start = index;
        if (events[start - 1]?.type === 'lookup') start -= 1;
        if (events[start - 1]?.type === 'require_output') start -= 1;
        return { focus: event, start };
      });
    const finalize = events.findIndex((event) => event.type === 'finalize');
    const steps = [{ start: 0 }, ...selections, { start: finalize, complete: true }];
    return steps.map((step, index) => ({ ...step, end: steps[index + 1]?.start ?? events.length }));
  }

  function renderReadableTask(task) {
    const section = el('section', undefined, 'task-readable');
    section.append(el('h4', 'Task in plain English'));
    const definitions = el('dl');
    const add = (label, text) => definitions.append(el('dt', label), el('dd', text));
    const outputNames = {
      'strata.source': 'C++ project with Ascend source',
      'strata.binary': 'CPU executable',
      'strata.result.routing': 'expert IDs and routing weights',
      'strata.result.activation': 'activated values',
      'strata.result.aggregation': 'combined expert output',
    };
    const deliverables = task.required_outputs.map((kind) => {
      const output = DATA.graph.outputs[kind];
      const producer = buildActions.get(output?.node) ?? parts.get(output?.node)?.part;
      return outputNames[kind] ?? producer?.outputs[output?.port]?.name ?? kind;
    });
    add('Deliver', deliverables.join(', ') + '.');

    const { routing, activation, aggregation } = task.inputs ?? {};
    const vector = (values) => '[' + values.join(', ') + ']';
    if (routing) {
      const [count, top, ...scores] = routing.numeric_input.trim().split(/\s+/).map(Number);
      add('Select experts', 'Pick the top ' + top + ' of ' + count + ' experts scored ' + vector(scores) + '.');
    }
    if (activation) {
      const [length, ...values] = activation.numeric_input.trim().split(/\s+/).map(Number);
      add(
        'Run activation',
        'Use gate values ' +
          vector(values.slice(0, length)) +
          ' and up-projection values ' +
          vector(values.slice(length)) +
          '.',
      );
    }
    if (aggregation) {
      const supplied = Object.entries(aggregation.expert_outputs).map(
        ([id, values]) => 'Expert ' + id + ' ' + vector(values),
      );
      supplied.push('shared output ' + vector(aggregation.shared_output));
      add('Combine outputs', 'Use ' + supplied.join(', ') + '. Get the expert IDs and weights from Select experts.');
    }
    section.append(definitions);
    return section;
  }

  function renderComposeInputs(view) {
    const inputs = el('div', undefined, 'grid compose-inputs');
    const task = el('article');
    const submitted = DATA.composition.task;
    task.append(
      el('h3', 'Task'),
      el('p', submitted.description),
      details('Open the submitted task JSON', JSON.stringify(submitted, null, 2), 'task-json'),
      renderReadableTask(submitted),
    );
    const policy = el('article');
    policy.append(el('h3', 'Compose Policy'));
    const summary = el('ol', undefined, 'policy-summary');
    for (const section of DATA.composition.policy.split('\n## ').slice(1)) {
      const [heading, ...lines] = section.split('\n');
      const [, title] = heading.split(' | ');
      const rule = el('li');
      rule.append(el('strong', title));
      const example = lines
        .filter((line) => line.startsWith('> '))
        .map((line) => line.slice(2))
        .join(' ');
      if (example) rule.append(el('p', example));
      summary.append(rule);
    }
    policy.append(summary, details('Open the full Compose Policy', DATA.composition.policy, 'policy'));
    inputs.append(task, policy);
    view.append(inputs);
  }

  function composeLibraryGroups(project) {
    const catalog = DATA.catalog.find((entry) => entry.id === project.id);
    return (
      catalog?.groups ?? [
        {
          id: project.id,
          name: 'Registered subworkflows',
          parts: project.subworkflows.map((part) => ({ ...part, recorded_part: part.id })),
        },
      ]
    );
  }

  function renderComposeLibrary(focus, picked) {
    const panel = el('article', undefined, 'compose-library');
    panel.append(el('h3', 'Workflow Library'));
    const tree = el('div', undefined, 'compose-tree');
    const inspect = el('div', undefined, 'compose-library-inspect');
    let focused;
    let activePath;
    const folder = (key, name, expanded) => {
      const entry = el('details');
      entry.open = expanded || composeFolders.has(key);
      entry.append(el('summary', name));
      entry.addEventListener('toggle', () => {
        if (entry.open) composeFolders.add(key);
        else composeFolders.delete(key);
      });
      return entry;
    };
    for (const project of DATA.composition.library) {
      const root = folder(project.id, project.name, focus?.workflow === project.id);
      for (const group of composeLibraryGroups(project)) {
        const containsFocus = group.parts.some((part) => project.id + '.' + part.recorded_part === focus?.node);
        const branch = folder(project.id + '/' + group.id, group.name, containsFocus);
        for (const part of group.parts) {
          const id = project.id + '.' + part.recorded_part;
          const registered = parts.get(id)?.part;
          const item = button(
            part.name,
            () => {
              inspect.replaceChildren(el('strong', part.name));
              if (registered) {
                const labels = Object.values(registered.outputs).map((output) => output.name);
                inspect.append(el('p', 'Provides ' + labels.join(', ') + '.'));
              } else if (part.output) {
                inspect.append(el('p', part.output));
              }
              if (part.code) inspect.append(details('Original function', part.code));
            },
            'compose-library-item',
            'catalog-part',
            project.id + '.' + part.id,
          );
          if (picked.has(id)) item.classList.add('compose-picked');
          if (focus?.node === id) {
            item.setAttribute('aria-current', 'true');
            focused = item;
            activePath = project.name + ' / ' + group.name;
          }
          branch.append(item);
        }
        root.append(branch);
      }
      tree.append(root);
    }
    if (activePath) panel.append(el('p', activePath, 'compose-library-path'));
    panel.append(tree, inspect);
    return { panel, tree, focused };
  }

  function renderComposeDecision(beat, events) {
    const panel = el('article', undefined, 'compose-decision');
    panel.append(el('h3', 'Planner decisions'));
    const group = events.slice(beat.start, beat.end);
    if (beat.complete) {
      panel.append(
        el('p', 'Task Graph ready', 'compose-decision-title'),
        el('p', 'The graph places each producer before the steps that need its output.'),
      );
      const unused = events.filter((event) => event.type === 'leave_unselected');
      if (unused.length)
        panel.append(el('p', 'Left in the Library: ' + unused.map((event) => event.name).join(', ') + '.'));
    } else if (!beat.focus) {
      panel.append(
        el('p', 'Read the task and policy', 'compose-decision-title'),
        el('p', 'The Planner starts with a requested result, then follows any missing inputs back to the Library.'),
      );
    } else {
      const selected = beat.focus;
      const action = buildActions.get(selected.node);
      panel.append(el('p', (action ? 'Schedule ' : 'Pick ') + selected.name, 'compose-decision-title'));
      const reason = el('dl', undefined, 'function-contract compose-reason');
      const requester = rows.get(selected.consumer)?.name;
      reason.append(
        el('dt', requester ? 'Input needed' : 'Task asks for'),
        el('dd', requester ? requester + ' needs ' + selected.label : selected.label),
      );
      if (action) {
        reason.append(el('dt', 'Build action'), el('dd', 'This built-in step produces the requested output.'));
      } else {
        reason.append(
          el('dt', 'Library match'),
          el('dd', parts.get(selected.node).project.name + ' provides that exact output.'),
        );
      }
      const needs = group.filter((event) => event.type === 'need_input');
      for (const need of needs) {
        const reuse = group.find((event) => event.type === 'reuse' && event.kind === need.kind);
        reason.append(
          el('dt', reuse ? 'Reuse' : 'Still needs'),
          el('dd', reuse ? rows.get(reuse.node).name + ' supplies ' + need.label : need.label),
        );
      }
      panel.append(reason);
    }
    const links = group.filter((event) => event.type === 'bind');
    if (links.length) {
      panel.append(el('h4', 'Connect the steps'));
      const list = el('ul', undefined, 'compose-connects');
      for (const link of links) {
        list.append(el('li', rows.get(link.from).name + ' → ' + link.label + ' → ' + rows.get(link.to).name));
      }
      panel.append(list);
    }
    const filter = group.find((event) => event.type === 'set_filter');
    if (filter) {
      const selection = el('details');
      selection.append(
        el('summary', 'Filter to the selected STRATA source functions'),
        el('p', filter.functions.join(', ')),
        el('pre', filter.pattern),
      );
      panel.append(selection);
    }
    if (group.length) panel.append(details('Inspect recorded decisions', JSON.stringify(group, null, 2), 'decisions'));
    const controls = el('div', undefined, 'actions');
    const previous = button(
      'Previous',
      () => {
        composeStep -= 1;
        refreshCompose();
      },
      undefined,
      'decision-previous',
    );
    previous.disabled = composeStep === 0;
    controls.append(previous);
    if (beat.complete)
      controls.append(
        button(
          'Restart planning',
          () => {
            composeStep = 0;
            refreshCompose();
          },
          undefined,
          'decision-restart',
        ),
      );
    else {
      controls.append(
        button(
          composeStep ? 'Next decision' : 'Start planning',
          () => {
            composeStep += 1;
            refreshCompose();
          },
          'primary',
          'decision-next',
        ),
      );
      controls.append(
        button(
          'Show full graph',
          () => {
            composeStep = composeSteps.length - 1;
            refreshCompose();
            view.querySelector('.compose-graph').scrollIntoView({ block: 'start' });
          },
          undefined,
          'show-graph',
        ),
      );
    }
    panel.append(controls);
    return panel;
  }

  function renderComposedGraph(anchor, events, complete) {
    anchor.append(el('h3', 'Task Graph'));
    const added = new Set(events.filter((event) => event.type === 'add_node').map((event) => event.node));
    const planned = DATA.graph.nodes.filter((node) => added.has(node.id));
    if (!planned.length) {
      anchor.append(el('p', 'Steps and links appear here as the Planner resolves inputs.'));
      return;
    }
    const scroller = el('div', undefined, 'diagram-scroll');
    const diagram = el('div', undefined, 'diagram');
    const canvas = el('canvas');
    canvas.setAttribute('aria-hidden', 'true');
    diagram.append(canvas);
    const build = planned.filter((node) => node.step.workflow !== 'strata');
    const functions = planned.filter((node) => node.step.workflow === 'strata');
    const columns = build.map((node) => [node]);
    if (functions.length) columns.push(functions);
    diagram.style.gridTemplateColumns = 'repeat(' + columns.length + ',minmax(0,1fr))';
    diagram.style.minWidth = columns.length * 195 + 'px';
    const edges = events.filter((event) => event.type === 'bind');
    const cards = new Map();
    for (const column of columns) {
      const lane = el('div', undefined, 'diagram-lane');
      for (const node of column) {
        const project = parts.get(node.id)?.project;
        const card = el('article', undefined, 'plan-node ' + (project?.id ?? 'build-action'));
        card.append(
          el('p', project?.name ?? 'Build action', 'node-origin'),
          el('h3', node.name),
          el('p', DATA.composition.selections[node.id].output, 'node-output'),
        );
        const routing = edges.find((edge) => edge.to === node.id && edge.input === 'routing');
        if (routing)
          card.append(el('p', routing.label + ' from ' + rows.get(routing.from).name + '.', 'routing-input'));
        cards.set(node.id, card);
        lane.append(card);
      }
      diagram.append(lane);
    }
    scroller.append(diagram);
    anchor.append(scroller);
    diagramObserver = new ResizeObserver(() => drawPlan(canvas, cards, edges));
    diagramObserver.observe(diagram);
    for (const card of cards.values()) diagramObserver.observe(card);
    if (complete) {
      const final = events.find((event) => event.type === 'finalize');
      const order = final.node_order.map((id) => rows.get(id).name);
      const graphFile = DATA.scheduling?.graphFile;
      anchor.append(
        el('h4', 'Execution order'),
        el('p', order.join(' → ')),
        details(
          'Open the Task Graph JSON',
          typeof graphFile?.content === 'string' ? graphFile.content : JSON.stringify(DATA.graph, null, 2),
          'graph-json',
        ),
        button('Open Scheduling', () => navigate('scheduling'), 'primary', 'open-scheduling'),
      );
    }
  }

  function refreshCompose() {
    const panels = view.querySelector('.compose-workspace');
    const beat = composeSteps[composeStep];
    const events = DATA.composition.events;
    const prefix = events.slice(0, beat.end);
    const picked = new Set(prefix.filter((event) => event.type === 'select').map((event) => event.node));
    const { panel, tree, focused } = renderComposeLibrary(beat.focus, picked);
    panels.replaceChildren(panel, renderComposeDecision(beat, events));
    if (focused) tree.scrollTop = focused.getBoundingClientRect().top - tree.getBoundingClientRect().top - 32;
    const graph = view.querySelector('.compose-graph');
    graph.replaceChildren();
    diagramObserver?.disconnect();
    diagramObserver = undefined;
    renderComposedGraph(graph, prefix, beat.complete);
  }

  function renderPlan(view) {
    view.append(el('h2', 'Compose the workflow'));
    renderComposeInputs(view);
    view.append(el('div', undefined, 'compose-workspace'), el('section', undefined, 'compose-graph'));
    refreshCompose();
  }

  function renderScheduling(view) {
    view.append(el('h2', 'Scheduling'));
    const handoff = DATA.events.find((event) => event.type === 'scheduler.started');
    const plan = DATA.events.find((event) => event.type === 'scheduler.assignments_ready');
    const planned = Array.isArray(plan?.payload?.assignments);
    const assignments = (
      planned
        ? plan.payload.assignments
        : DATA.events.filter((event) => event.type === 'scheduler.dispatched').map((event) => event.payload)
    ).filter((assignment) => typeof assignment?.node_id === 'string' && typeof assignment.builder === 'string');

    const receipt = DATA.scheduling;
    const handoffCard = el('article');
    handoffCard.dataset.testid = 'workflow-demo-guided-scheduling-handoff';
    handoffCard.append(el('h3', handoff ? 'Task Graph received by Scheduler' : 'Recorded Task Graph'));
    const graphFile = receipt?.graphFile;
    if (typeof graphFile?.name === 'string' && typeof graphFile.content === 'string') {
      const download = el('a', 'Download JSON', 'download');
      download.dataset.testid = 'workflow-demo-guided-scheduling-graph-download';
      download.download = graphFile.name;
      download.href = 'data:application/json;charset=utf-8,' + encodeURIComponent(graphFile.content);
      handoffCard.append(
        el('code', graphFile.name),
        details('Open the Task Graph JSON file', graphFile.content, 'scheduling-graph-file'),
        download,
      );
      if (typeof graphFile.sha256 === 'string') {
        const sameFile = graphFile.sha256 === handoff?.payload?.graph_input?.sha256;
        const digestLabel = sameFile ? 'Matching Planner and Scheduler SHA-256' : 'SHA-256 of the Task Graph file';
        handoffCard.append(details(digestLabel, graphFile.sha256, 'scheduling-graph-sha256'));
      }
    } else {
      const receivedName = handoff?.payload?.graph_input?.filename;
      if (typeof receivedName === 'string') handoffCard.append(el('code', receivedName));
      handoffCard.append(
        details('Open the recorded Task Graph', JSON.stringify(DATA.graph, null, 2), 'scheduling-recorded-graph'),
      );
    }

    const checks = Array.isArray(receipt?.validation?.checks)
      ? receipt.validation.checks.filter((check) => typeof check === 'string')
      : [];
    if (checks.length) {
      const grid = el('div', undefined, 'grid');
      const validation = el('article');
      validation.dataset.testid = 'workflow-demo-guided-scheduling-checks';
      const list = el('ul', undefined, 'function-list');
      for (const check of checks) list.append(el('li', check));
      validation.append(el('h3', 'Checks before dispatch'), list);
      const m1Checks = [];
      const { dependency_check: dependencyCheck, dispatch_gate: dispatchGate } = handoff?.payload ?? {};
      if (dependencyCheck === 'jiuwenswarm.research.binding.kahn_order') {
        m1Checks.push('Check that task dependencies have a valid order\n' + dependencyCheck);
      }
      if (dispatchGate === 'jiuwenswarm.research.scheduler_dependencies.unaccepted_predecessors') {
        m1Checks.push('Wait for upstream steps to pass before dispatch\n' + dispatchGate);
      }
      if (m1Checks.length) validation.append(details('M1 checks used here', m1Checks.join('\n\n'), 'scheduling-m1'));
      grid.append(handoffCard, validation);
      view.append(grid);
    } else {
      view.append(handoffCard);
    }

    if (assignments.length) {
      const dispatch = el('article');
      dispatch.dataset.testid = 'workflow-demo-guided-scheduling-dispatch';
      dispatch.append(el('h3', planned ? 'Builder assignment plan' : 'Recorded Builder dispatches'));
      if (planned) dispatch.append(el('p', 'The Scheduler sends each step to its Builder once its inputs are ready.'));
      const list = el('ol', undefined, 'scheduling-assignments');
      for (const assignment of assignments) {
        const { node_id: id, worker_type: workerType, builder, execution_reason: reason, dependencies } = assignment;
        const item = el('li');
        item.dataset.testid = 'workflow-demo-guided-scheduling-assignment';
        item.dataset.variant = id;
        if (typeof workerType === 'string') item.dataset.workerType = workerType;
        const arrow = el('span', '→');
        arrow.setAttribute('aria-hidden', 'true');
        const heading = el('div', undefined, 'scheduling-assignment-heading');
        heading.append(el('span', rows.get(id)?.name ?? id), arrow, el('strong', builder));
        item.append(heading);
        if (typeof reason === 'string') item.append(el('p', reason));
        if (Array.isArray(dependencies) && dependencies.length) {
          const names = dependencies
            .filter((dependency) => typeof dependency === 'string')
            .map((dependency) => rows.get(dependency)?.name ?? dependency);
          if (names.length) item.append(el('p', 'After ' + names.join(', ')));
        }
        list.append(item);
      }
      dispatch.append(list);
      view.append(dispatch);
    } else if (!handoff) {
      view.append(el('p', 'This recording contains the Task Graph and construction events.'));
    }

    view.append(button('Replay the build', () => navigate('construction'), 'primary', 'replay-build'));
  }

  function stepTitle(event) {
    const kinds = Object.values(event.payload.outputs).map((output) => output.kind);
    if (kinds.includes('strata.operation_selection')) return 'Select the functions';
    if (kinds.includes('strata.source')) return 'Generate Ascend C++';
    if (kinds.includes('strata.binary')) return 'Compile on CPU';
    return rows.get(event.node).name;
  }

  function sourceDownload(label) {
    const download = el('a', label, 'download');
    download.dataset.testid = 'workflow-demo-guided-download-product';
    download.download = 'STRATA-Cpp-source.zip';
    download.href = 'data:application/zip;base64,' + DATA.archive;
    return download;
  }

  function renderReplayResult(event) {
    const box = el('article', undefined, 'replay-result');
    box.append(el('h3', stepTitle(event)));
    const earlier = DATA.events.filter((entry) => entry.node === event.node && entry.sequence <= event.sequence);
    const dispatch = DATA.events.find(
      (entry) =>
        entry.type === 'scheduler.dispatched' &&
        entry.payload?.node_id === event.node &&
        entry.sequence <= event.sequence,
    );
    if (typeof dispatch?.payload?.builder === 'string') {
      const builder = el('p', 'Dispatched to ' + dispatch.payload.builder);
      builder.dataset.testid = 'workflow-demo-guided-construction-builder';
      box.append(builder);
    }
    for (const output of Object.values(event.payload.outputs)) {
      if (output.kind === 'strata.source') {
        box.append(el('p', 'Generated project'), el('code', output.name, 'artifact-name'));
        const files = el('ul', undefined, 'function-list');
        for (const name of Object.keys(DATA.comparisons).sort()) {
          const item = el('li');
          item.append(el('code', name));
          files.append(item);
        }
        box.append(files);
        const actions = el('div', undefined, 'actions');
        actions.append(
          button('Open the generated C++', () => navigate('product'), undefined, 'open-product'),
          sourceDownload('Download source project'),
        );
        box.append(actions);
      } else if (output.kind === 'strata.binary') {
        box.append(el('p', 'Compiled CPU executable'), el('code', output.name, 'artifact-name'));
      }
    }
    const selection = earlier.find((entry) => entry.type === 'operations.selected');
    if (selection) {
      box.append(el('p', 'GoogleTest matched these original STRATA functions. The C++ generator used this list.'));
      const list = el('ul', undefined, 'function-list');
      for (const id of selection.payload.selected) {
        const item = el('li');
        item.append(el('code', id.split(':').at(-1)));
        list.append(item);
      }
      box.append(list);
    }
    const result = earlier.find((entry) => entry.type === 'operation.result');
    if (result) {
      const output = result.payload.output;
      const routing = earlier.find((entry) => entry.type === 'aggregation.input_ready');
      if (routing)
        box.append(
          el('p', 'Uses expert IDs ' + routing.payload.experts.join(', ') + ' and their weights from Select experts.'),
        );
      if (output.ids)
        box.append(el('p', 'Expert IDs: ' + output.ids.join(', ')), el('p', 'Weights: ' + output.weights.join(', ')));
      if (output.output) box.append(el('p', 'Output: ' + output.output.join(', ')));
      box.append(details('Runtime input', result.payload.input));
    }
    const commands = DATA.commands.filter(
      (command) => command.node === event.node && command.sequence <= event.sequence,
    );
    if (commands.length)
      box.append(
        details(
          'Commands and terminal output',
          commands
            .map((command) => '$ ' + command.argv.join(' ') + '\n' + command.output + '\nExit ' + command.exit)
            .join('\n\n'),
        ),
      );
    return box;
  }

  function renderReplay(view) {
    view.append(el('h2', 'Follow the build'));
    const layout = el('div', undefined, 'replay-layout');
    const timeline = el('ol', undefined, 'replay-timeline');
    for (const [index, event] of trace.entries()) {
      const item = el('li');
      const stage = button(
        stepTitle(event),
        () => {
          replayStep = index;
          render();
        },
        undefined,
        'construction-stage',
        event.node,
      );
      stage.disabled = index >= position;
      if (index === replayStep) stage.setAttribute('aria-current', 'step');
      item.append(stage);
      timeline.append(item);
    }
    layout.append(timeline, renderReplayResult(trace[replayStep]));
    view.append(layout);
    const controls = el('div', undefined, 'actions');
    const next = trace[position];
    if (next)
      controls.append(
        button(
          'Next: ' + stepTitle(next),
          () => {
            replayStep = position;
            position += 1;
            render();
          },
          'primary',
          'construction-next',
        ),
      );
    else controls.append(button('Open the generated C++', () => navigate('product'), 'primary', 'finish-open-product'));
    const restart = button(
      'Restart',
      () => {
        position = 1;
        replayStep = 0;
        render();
      },
      undefined,
      'construction-restart',
    );
    restart.disabled = position === 1;
    controls.append(restart);
    view.append(controls);
  }

  function buildProductTree(paths) {
    const root = { folders: new Map(), files: [] };
    for (const path of paths.sort()) {
      const segments = path.split('/');
      const name = segments.pop();
      let branch = root;
      for (const segment of segments) {
        if (!branch.folders.has(segment)) branch.folders.set(segment, { folders: new Map(), files: [] });
        branch = branch.folders.get(segment);
      }
      branch.files.push({ name, path });
    }
    return root;
  }

  function renderProductTree(branch, parentPath, selectFile, selectors) {
    const list = el('ul', undefined, 'product-tree-list');
    for (const [name, children] of branch.folders) {
      const path = parentPath + name + '/';
      const item = el('li');
      const folder = el('details');
      folder.open = openProductFolders.has(path);
      folder.addEventListener('toggle', () => {
        if (folder.open) openProductFolders.add(path);
        else openProductFolders.delete(path);
      });
      const label = el('summary', name);
      label.dataset.testid = 'workflow-demo-guided-folder';
      label.dataset.variant = path;
      folder.append(label, renderProductTree(children, path, selectFile, selectors));
      item.append(folder);
      list.append(item);
    }
    for (const { name, path } of branch.files) {
      const item = el('li');
      const selector = button(name, () => selectFile(path), 'product-file', 'file', path);
      if (file === path) selector.setAttribute('aria-current', 'true');
      selectors.set(path, selector);
      item.append(selector);
      list.append(item);
    }
    return list;
  }

  function productCode(content, path) {
    const code = el('pre');
    code.tabIndex = 0;
    code.setAttribute('aria-label', path);
    code.append(el('code', content));
    return code;
  }

  function renderProductPreview(preview) {
    const comparison = DATA.comparisons[file];
    preview.replaceChildren();
    const heading = el('div', undefined, 'product-file-heading');
    heading.append(el('h3', file, 'product-path'));
    let toggle;
    if (comparison) {
      toggle = button(
        compare ? 'Show generated source' : 'Compare with STRATA',
        () => {
          compare = !compare;
          renderProductPreview(preview)?.focus();
        },
        undefined,
        'compare-source',
      );
      heading.append(toggle);
    }
    preview.append(heading);
    if (!compare || !comparison) {
      preview.append(productCode(DATA.files[file], file));
    } else {
      const grid = el('div', undefined, 'grid product-comparison');
      for (const [label, path, content] of [
        ['Original STRATA', comparison.source_path, comparison.source_code],
        ['Generated Ascend C++', file, DATA.files[file]],
      ]) {
        const pane = el('section');
        pane.append(el('h3', label), el('code', path), productCode(content, path));
        grid.append(pane);
      }
      preview.append(grid);
    }
    return toggle;
  }

  function renderProduct(view) {
    const heading = el('div', undefined, 'product-heading');
    const intro = el('div');
    intro.append(el('h2', 'Product'), el('p', 'STRATA C++ project with Ascend source and a recorded CPU build.'));
    heading.append(intro, sourceDownload('Download ZIP'));

    const workspace = el('div', undefined, 'product-workspace');
    const tree = el('nav', undefined, 'product-tree');
    tree.setAttribute('aria-label', 'Project files');
    tree.append(el('h3', DATA.projectName + '/'));
    const treeBody = el('div', undefined, 'product-tree-body');
    const preview = el('section', undefined, 'product-preview');
    preview.setAttribute('aria-label', 'File preview');
    preview.dataset.testid = 'workflow-demo-guided-file-preview';
    const selectors = new Map();
    const selectFile = (path) => {
      if (path === file) return;
      selectors.get(file)?.removeAttribute('aria-current');
      file = path;
      compare = false;
      selectors.get(file).setAttribute('aria-current', 'true');
      renderProductPreview(preview);
    };
    treeBody.append(renderProductTree(productTree, '', selectFile, selectors));
    treeBody.addEventListener('scroll', () => {
      productTreeScroll = treeBody.scrollTop;
    });
    tree.append(treeBody);
    workspace.append(tree, preview);
    view.append(heading, workspace);
    renderProductPreview(preview);
    treeBody.scrollTop = productTreeScroll;
  }

  const screens = {
    projects: renderProjects,
    library: renderLibrary,
    compose: renderPlan,
    scheduling: renderScheduling,
    construction: renderReplay,
    product: renderProduct,
  };
  const shell = el('section', undefined, 'guided-replay');
  shell.dataset.testid = 'workflow-demo-guided-surface';
  const nav = el('nav', undefined, 'guided-replay-navigation');
  nav.setAttribute('aria-label', 'Demo steps');
  nav.dataset.testid = 'workflow-demo-guided-navigation';
  const view = el('div', undefined, 'guided-replay-content');
  const navigation = steps.map((step) => button(step.label, () => navigate(step.id), undefined, 'nav-' + step.id));
  nav.append(...navigation);
  shell.append(nav, view);

  function render() {
    diagramObserver?.disconnect();
    diagramObserver = undefined;
    const libraryScroll = view.querySelector('.library-outline')?.scrollTop;
    view.replaceChildren();
    screens[state](view);
    if (libraryScroll) {
      const outline = view.querySelector('.library-outline');
      if (outline) outline.scrollTop = libraryScroll;
    }
    navigation.forEach((selector, index) => {
      if (steps[index].id === state) selector.setAttribute('aria-current', 'step');
      else selector.removeAttribute('aria-current');
    });
  }

  function navigate(target) {
    state = target;
    render();
    view.scrollTop = 0;
  }

  render();
  container.replaceChildren(shell);
  return () => {
    diagramObserver?.disconnect();
    shell.remove();
  };
}
