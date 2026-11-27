"""What the scheduler agent reads before it finalizes one node, and what it reads on demand. Pure reads.

``finalize_brief`` (``factory.scheduler.brief``) gives the scheduler as much of the run as it can use:

* ``task``: the task record and the full task contract (purpose, scope, arms, workload, measurement,
  correctness, acceptance, limits, execution, provenance), and every node contract of its revision;
* ``plan``: every node of the task graph, with this node marked, and this node's direct neighbours;
* ``briefing``: the planner's notes for this node (node contract field ``briefing``);
* ``preliminary``, ``draft_final`` and ``inputs`` (as before);
* ``upstream``: for each done node, its admitted final contract with rationale and diff, its accepted node checks
  in full, the evidence records it cites and its capped runs;
* ``history``: operator records (graph changes, notes, excuses, halts, inputs, host readings), every refused
  proposal of the task, and for this node contract earlier finals, failures with their checks and capped runs;
* ``machine``: the machine state file and the job queue (this task's attempts and the shared jobq);
* ``capsules``: for each capsule the scheduler may bind, its cc.yaml, docs (SKILL.md and its skill and method
  materials), verification units, file list and where this run bound it before.

Every file and record is bounded (``FILE_CHARS``, ``RECORD_CHARS``); a cut one says so and names the call that
reads it whole: ``factory.scheduler.capsule`` for capsule files, ``factory.scheduler.evidence`` for records. The
whole brief is kept under ``BRIEF_CHARS`` by tightening those bounds step by step (``trimmed`` says how far).
"""
from __future__ import annotations

import json
import os
from pathlib import Path, PurePosixPath

FILE_CHARS = 60000           # one capsule file in the brief, and one read of factory.scheduler.capsule
RECORD_CHARS = 8000          # one evidence record or check detail in the brief
BRIEF_CHARS = 400000         # the whole brief
READ_CHARS = 200000          # one read of factory.scheduler.evidence
LIST_LIMIT = 500             # files listed per capsule
QUEUE_LIMIT = 40             # jobs listed from the shared queue
# Bounds tried in order until the brief fits BRIEF_CHARS: per capsule file, per record of this node and its direct
# predecessors, per record of the other done nodes. The other nodes' records shrink first, the capsule docs last. A
# file bound of 0 keeps a capsule's file list and verification units and leaves its doc texts to factory.scheduler.capsule.
LEVELS = ((FILE_CHARS, RECORD_CHARS, RECORD_CHARS), (FILE_CHARS, RECORD_CHARS, 3000), (FILE_CHARS, RECORD_CHARS, 1200),
          (20000, 4000, 800), (6000, 2000, 500), (2000, 1000, 300), (0, 600, 200))
SKIP_PARTS = {'.git', '.venv', '__pycache__', '.pytest_cache', '.cc-state', '.mypy_cache', '.ruff_cache'}


# -- bounded values ------------------------------------------------------------------------------------------

def _size(value):
    return len(json.dumps(value, ensure_ascii=False, default=str))


def _cut_text(text, limit, how):
    text = '' if text is None else str(text)
    if len(text) <= limit:
        return dict(text=text)
    return dict(text=text[:limit], cut=f'Cut at {limit} of {len(text)} characters. {how}')


def _bounded(value, limit, how):
    """The value itself when its JSON fits ``limit``, else a cut JSON preview that says how to read it whole."""
    if _size(value) <= limit:
        return value
    text = json.dumps(value, ensure_ascii=False, default=str)
    return dict(preview=text[:limit], cut=f'Cut at {limit} of {len(text)} characters of JSON. {how}')


def _evidence_how(record_id):
    return f'Read it whole with factory.scheduler.evidence {{"id": "{record_id}"}}.'


# -- capsules ------------------------------------------------------------------------------------------------

def ccs_root():
    return Path(__file__).with_name('ccs')


def _read_text(path):
    return path.read_bytes().decode('utf-8', errors='replace').replace('\r\n', '\n')


def _roles(folder):
    try:
        return json.loads(_read_text(folder / 'roles.json')).get('materials') or {}
    except (OSError, ValueError, AttributeError):
        return {}


def doc_paths(folder, declaration):
    """The capsule's own docs in reading order: SKILL.md, then its skill materials, then its method materials."""
    paths = ['SKILL.md'] if (folder / 'SKILL.md').is_file() else []
    materials, roles = declaration.get('materials') or {}, _roles(folder)
    for role in ('skill', 'method'):
        paths += [str(m['path']) for name, m in materials.items()
                  if roles.get(name) == role and isinstance(m, dict) and m.get('path')]
    if not paths:
        paths = [name for name in ('METHOD.md', 'README.md') if (folder / name).is_file()]
    return list(dict.fromkeys(p for p in paths if (folder / p).is_file()))


def doc_purpose(folder, declaration):
    """A one-paragraph purpose from the capsule's first doc: its front-matter description or first paragraph."""
    for relative in doc_paths(folder, declaration)[:1]:
        try:
            text = _read_text(folder / relative)
        except OSError:
            return ''
        if text.startswith('---\n'):
            head, _, text = text[4:].partition('\n---')
            for line in head.splitlines():
                if line.startswith('description:'):
                    return line.partition(':')[2].strip()
        for block in text.split('\n\n'):
            block = block.strip()
            if block and not block.startswith(('#', '---', '```', '|')):
                return ' '.join(block.split())
    return ''


def _files(folder):
    rows = []
    for item in sorted(folder.rglob('*')):
        relative = item.relative_to(folder)
        if any(part in SKIP_PARTS for part in relative.parts) or item.is_symlink() or not item.is_file():
            continue
        rows.append(dict(path=relative.as_posix(), bytes=item.stat().st_size))
    return rows


def _verification(folder, declaration):
    """The capsule's verification unit documents, by path (VERIFICATION-UNITS.json and declared *VERIF*.json)."""
    paths = [str(m['path']) for m in (declaration.get('materials') or {}).values()
             if isinstance(m, dict) and str(m.get('path', '')).endswith('.json') and 'VERIF' in str(m['path']).upper()]
    if (folder / 'VERIFICATION-UNITS.json').is_file():
        paths.append('VERIFICATION-UNITS.json')
    found = {}
    for relative in dict.fromkeys(paths):
        try:
            found[relative] = json.loads(_read_text(folder / relative))
        except (OSError, ValueError):
            continue
    return found


def _unit_names(documents):
    names = []
    for document in documents.values():
        for unit in (document.get('units') or []) if isinstance(document, dict) else []:
            name = unit.get('id') if isinstance(unit, dict) else unit if isinstance(unit, str) else None
            if name and name not in names:
                names.append(name)
    return names


def capsule_view(cc_id, entry, file_chars=FILE_CHARS):
    """One capsule as the scheduler reads it in the brief."""
    folder = ccs_root() / entry['folder']
    how = 'Read it whole with factory.scheduler.capsule {"id": "%s", "path": "%s"}.'
    import yaml
    text = _read_text(folder / 'cc.yaml')
    declaration = yaml.safe_load(text) or {}
    roles = _roles(folder)
    units = _verification(folder, declaration)
    view = dict(entry, cc_yaml=dict(path='cc.yaml', **_cut_text(text, max(file_chars, 2000), how % (cc_id, 'cc.yaml'))),
                materials={name: dict(path=m.get('path'), role=roles.get(name, 'unlisted'))
                           for name, m in (declaration.get('materials') or {}).items() if isinstance(m, dict)},
                verification_units=_unit_names(units),
                verification={path: _bounded(doc, max(file_chars, 2000), how % (cc_id, path)) for path, doc in units.items()},
                files=_files(folder)[:LIST_LIMIT])
    docs = []
    for relative in doc_paths(folder, declaration):
        try:
            body = _read_text(folder / relative)
        except OSError:
            continue
        if file_chars:
            docs.append(dict(path=relative, **_cut_text(body, file_chars, how % (cc_id, relative))))
        else:
            docs.append(dict(path=relative, chars=len(body), cut='Left out to keep the brief bounded. ' + how % (cc_id, relative)))
    view['docs'] = docs
    return view


def capsule_read(cc_id, path=None, offset=0):
    """factory.scheduler.capsule: the files of one catalog capsule, or one text file from it (FILE_CHARS from
    ``offset``). Read-only; the path stays inside the capsule folder."""
    from .scheduler import catalog
    known = catalog()
    if not isinstance(cc_id, str) or cc_id not in known:
        raise ValueError(f'Unknown capsule: {cc_id}')
    root = (ccs_root() / known[cc_id]['folder']).resolve()
    if path is None or path in ('', '.'):
        files = _files(root)
        return dict(id=cc_id, version=known[cc_id]['version'], files=files[:LIST_LIMIT],
                    **({'more_files': len(files) - LIST_LIMIT} if len(files) > LIST_LIMIT else {}))
    if not isinstance(path, str) or '\0' in path or '\\' in path:
        raise ValueError('path must be a relative path inside the capsule folder, with / separators')
    relative = PurePosixPath(path)
    if not relative.parts or relative.is_absolute() or '..' in relative.parts or ':' in relative.parts[0] \
            or any(part in SKIP_PARTS for part in relative.parts):
        raise ValueError('path must be a relative path inside the capsule folder')
    target = root.joinpath(*relative.parts)
    if target.is_symlink() or not target.is_file():
        raise ValueError(f'No file {path} in capsule {cc_id}')
    target = target.resolve()
    if not target.is_relative_to(root):
        raise ValueError('path must stay inside the capsule folder')
    data = target.read_bytes()
    if b'\0' in data[:8192]:
        raise ValueError(f'{path} is not a text file')
    text = data.decode('utf-8', errors='replace').replace('\r\n', '\n')
    return dict(id=cc_id, version=known[cc_id]['version'], path=relative.as_posix(), bytes=len(data),
                **_page(text, offset, FILE_CHARS))


def _page(text, offset, limit):
    if type(offset) is not int or offset < 0:
        raise ValueError('offset must be a nonnegative integer')
    page = dict(offset=offset, chars=len(text), text=text[offset:offset + limit])
    if offset + limit < len(text):
        page['next_offset'] = offset + limit
    return page


# -- evidence ------------------------------------------------------------------------------------------------

def evidence_read(store, task_id, record_id, offset=0):
    """factory.scheduler.evidence: one record of this task in full (an observation, artifact, attempt, decision),
    READ_CHARS from ``offset``. An artifact's text is its whole verified content, not the 64 KiB preview."""
    if not isinstance(record_id, str) or not record_id:
        raise ValueError('id must name a record of this task')
    record = store.read(task_id, record_id)
    if 'location' in record and 'sha256' in record:  # an artifact
        record.pop('text_preview', None)
        record.pop('preview_truncated', None)
        data = store.artifact_bytes(task_id, record_id)
        if b'\0' in data[:8192]:
            return dict(id=record_id, record=record, text=None, note='Binary artifact; only its record is shown.')
        return dict(id=record_id, record=record, **_page(data.decode('utf-8', errors='replace'), offset, READ_CHARS))
    text = json.dumps(record, ensure_ascii=False, indent=1, default=str)
    if offset == 0 and len(text) <= READ_CHARS:
        return dict(id=record_id, record=record)
    return dict(id=record_id, record_json=_page(text, offset, READ_CHARS))


def _record(host, task_id, record_id, limit):
    try:
        record = host.read(task_id, record_id)
    except Exception as exc:  # noqa: BLE001 - a missing record is reported, the brief goes on
        return dict(id=record_id, unavailable=str(exc)[:300])
    if 'text_preview' in record:
        media = str(record.get('media_type', ''))
        if media.startswith('text/') or media in ('application/json', 'application/x-ndjson'):
            record = dict(record, text_preview=record['text_preview'][:max(200, limit // 2)])
        else:  # a binary artifact: its record only
            record = {k: v for k, v in record.items() if k not in ('text_preview', 'preview_truncated')}
    return dict(id=record_id, record=_bounded(record, limit, _evidence_how(record_id)))


def _observations(host, task_id, kind):
    rows = host._db.execute('SELECT obs_id, "values", source_artifacts, created FROM observations WHERE task_id=? AND kind=? '
                            'ORDER BY created, rowid', (task_id, kind))
    return [(obs_id, json.loads(values), json.loads(artifacts or '[]'), created) for obs_id, values, artifacts, created in rows]


def _artifact_sizes(host, task_id, ids):
    out = {}
    for aid in ids:
        row = host._db.execute('SELECT size, media_type FROM artifacts WHERE task_id=? AND artifact_id=?',
                               (task_id, aid)).fetchone()
        out[aid] = dict(bytes=row[0], media_type=row[1]) if row else None
    return out


def capped_runs(host, task_id, node_id, limit):
    """The capped runs that named this node: recipe, arguments, outcome, time, memory, result and output files."""
    runs = []
    for obs_id, doc, artifacts, _ in _observations(host, task_id, 'capped_run'):
        if doc.get('node_id') != node_id:
            continue
        run = dict(id=obs_id, recipe=doc.get('recipe'), args=_bounded((doc.get('request') or {}).get('args'), limit,
                                                                    _evidence_how(obs_id)),
                   outcome=doc.get('outcome'), error=doc.get('error'), seconds=doc.get('seconds'),
                   memory_cap=doc.get('memory_cap'), peak_memory_bytes=doc.get('peak_memory_bytes'),
                   min_available_bytes=doc.get('min_available_bytes'), attempt_id=doc.get('attempt_id'),
                   result=_bounded(doc.get('result'), limit, _evidence_how(obs_id)),
                   artifacts=_artifact_sizes(host, task_id, artifacts))
        if doc.get('replayed_from'):
            run['replayed_from'] = doc['replayed_from']
        runs.append(run)
    return runs


def _checks(host, task_id, node_id, limit):
    """Every node check of a graph node (passed or not), with its verifier checks."""
    from .node_check import checks_for
    out = []
    for c in checks_for(host, task_id, node_id):
        verifier = c.get('verifier') or {}
        out.append(dict(id=c['obs_id'], output=c.get('output', 'change'), state=c.get('state'), passed=c.get('passed'),
                        verifier=f"{verifier.get('cc')}.{verifier.get('capability')}" if verifier.get('cc') else None,
                        stage_reached=verifier.get('stage_reached'),
                        not_done_because=verifier.get('not_done_because'),
                        review=_bounded(c.get('review'), limit, _evidence_how(c['obs_id'])) if c.get('review') else None,
                        checks=[dict(name=k.get('name'), status=k.get('status'), detail=_cut_text(k.get('detail'), limit,
                                     _evidence_how(c['obs_id']))['text'])
                                for k in (verifier.get('checks') or [])]))
    return out


# -- the brief -----------------------------------------------------------------------------------------------

def _task_view(task, contract, contracts):
    record = {k: task[k] for k in ('task_id', 'objective', 'constraints', 'allowed_effects', 'target', 'budget',
                                   'contract_id', 'source', 'resources', 'operator_labels', 'initial_run_config')
              if task.get(k) not in (None, '', {}, [])}
    body = {k: v for k, v in dict(contract or {}).items() if k != 'extensions'}
    extensions = {k: v for k, v in ((contract or {}).get('extensions') or {}).items() if k != 'factory.node-contracts'}
    if extensions:
        body['extensions'] = extensions
    return dict(record=record, contract=body, node_contracts=(contracts or {}).get('nodes', []))


def _plan_view(host, task_id, graph, contracts, node_id, prelim):
    from .node_contract import node as contract_node_of
    from .scheduler import effective_contract
    plan = []
    for item in graph['nodes']:
        contract = effective_contract(host, task_id, item, contracts)[0] if item.get('node_contract') else None
        view = {k: item[k] for k in ('node_id', 'kind', 'state', 'depends_on', 'node_contract', 'final_contract', 'hold',
                                     'reason', 'outcome', 'retry_from', 'evidence_ids', 'attempt_ids') if item.get(k)}
        view['objective'] = (contract or {}).get('objective') or item.get('title')
        if item['node_id'] == node_id:
            view['this'] = True
        plan.append(view)

    def neighbour(name):
        contract = contract_node_of(contracts, name) or {}
        return dict(node_contract=name, kind=contract.get('kind'), objective=contract.get('objective'),
                    outputs=[dict(name=o['name'], kind=o['kind'], criteria=o.get('criteria', [])) for o in contract.get('outputs', [])],
                    **({'briefing': contract['briefing']} if contract.get('briefing') else {}))
    neighbours = dict(predecessors=[neighbour(p) for p in prelim.get('predecessors', [])])
    handoff = prelim.get('hands_to')
    if handoff == 'lab_manager':
        staged = (contracts or {}).get('staged_release')
        objective = ('The lab manager seals delivery for the graph measurement node.' if staged else
                     'The lab manager receives the delivered engine and runs the lab arms.')
        neighbours['hands_to'] = dict(node_contract=handoff, objective=objective)
    elif handoff == 'operator':
        neighbours['hands_to'] = dict(node_contract=handoff, objective='The operator receives the release verdict.')
    else:
        neighbours['hands_to'] = neighbour(handoff)
    return dict(rev=graph['rev'], nodes=plan), neighbours


def _upstream(host, task_id, graph, contracts, direct, limits):
    """Every done node: (record bound for this node's direct predecessors, record bound for the others)."""
    from .scheduler import accepted_checks, effective_contract, recorded_finals
    finals = {(r['node_id'], r['digest']): r for r in recorded_finals(host, task_id)}
    out = {}
    for item in graph['nodes']:
        if item['state'] != 'done' or not item.get('node_contract'):
            continue
        final, _ = effective_contract(host, task_id, item, contracts)
        record = finals.get((item['node_id'], item.get('final_contract')))
        limit = limits[0] if item['node_id'] in direct else limits[1]
        out[item['node_id']] = dict(
            node_contract=item['node_contract'], outcome=item.get('outcome'),
            **({'direct_predecessor': True} if item['node_id'] in direct else {}),
            final_contract=item.get('final_contract'), contract=final,
            **({'finalized': dict(rationale=record['rationale'], diff=record['diff'], by=record.get('by'),
                                  cc_versions=record.get('cc_versions'))} if record else {}),
            bound_ccs=((final or {}).get('work') or {}).get('bound_ccs'),
            accepted_checks=accepted_checks(host, task_id, item['node_id'], limit=500, detail_chars=limit),
            evidence=[_record(host, task_id, rid, limit) for rid in item.get('evidence_ids', [])],
            capped_runs=capped_runs(host, task_id, item['node_id'], limit))
    return out


def _operator_notes(host, task_id, limit):
    from .operator_notes import directory
    notes = []
    try:
        for path in directory(host.home, task_id).glob('*.json'):
            value = json.loads(path.read_text(encoding='utf-8'))
            notes.append(dict(note_id=value.get('note_id'), created=value.get('created'),
                              **_cut_text(value.get('text'), limit, 'The operator inbox holds the whole note.')))
    except (OSError, ValueError):
        pass
    return sorted(notes, key=lambda n: (n.get('created') or 0, n.get('note_id') or ''))


def _history(host, task_id, graph, node, prelim, limit):
    from .scheduler import FINAL_KIND, REFUSAL_KIND, operator_inputs, _failures
    operator = dict(
        graph_changes=[dict(rev=h['rev'], patch=_bounded(h.get('patch'), limit, ''), created=h.get('created'))
                       for h in graph.get('history', []) if h.get('origin') == 'operator'],
        notes=_operator_notes(host, task_id, limit),
        excused_attempts=[{**v, 'id': o} for o, v, _, _ in _observations(host, task_id, 'attempt_excused')],
        halts=[{**v, 'id': o} for o, v, _, _ in _observations(host, task_id, 'operator_halt')],
        inputs=operator_inputs(host, task_id, text_chars=limit),
        host_readings=[dict(id=o, values=_bounded(v, limit, _evidence_how(o)))
                       for o, v, _, _ in _observations(host, task_id, 'host_reading')][-10:])
    refusals = [dict(id=o, node_id=v['node_id'], by=v.get('by', 'scheduler-agent'), problems=v['problems'],
                     rationale=_cut_text(v.get('rationale'), limit, _evidence_how(o))['text'])
                for o, v, _, _ in _observations(host, task_id, REFUSAL_KIND)]
    failures, _ = _failures(host, task_id, graph, node['node_contract'])
    for failure in failures:
        failure['checks'] = _checks(host, task_id, failure['node_id'], limit)
        failure['capped_runs'] = capped_runs(host, task_id, failure['node_id'], limit)
    finals = [dict(id=o, node_id=v['node_id'], digest=v['digest'], by=v.get('by'), rationale=v['rationale'], diff=v['diff'],
                   final=_bounded(v['final'], 4 * limit, _evidence_how(o)), cc_versions=v.get('cc_versions'))
              for o, v, _, _ in _observations(host, task_id, FINAL_KIND) if v['node_contract'] == node['node_contract']]
    this = dict(failures=failures, earlier_finals=finals,
                checks=_checks(host, task_id, node['node_id'], limit),
                capped_runs=capped_runs(host, task_id, node['node_id'], limit))
    return dict(operator=operator, refusals=refusals, this_node=this)


def _queue(host, task_id):
    rows = host._db.execute('SELECT attempt_id, kind, state, request, started, ended FROM attempts WHERE task_id=? '
                            "AND state IN ('queued', 'running')", (task_id,)).fetchall()
    task_jobs = [dict(attempt_id=a, kind=k, state=s, node_id=json.loads(r or '{}').get('node_id'),
                      recipe=json.loads(r or '{}').get('recipe'), started=st, ended=en) for a, k, s, r, st, en in rows]
    shared, directory = None, os.environ.get('JOBQ_DIR')
    if directory:
        jobs = []
        try:
            for path in Path(directory).glob('job-*.json'):
                j = json.loads(path.read_text(encoding='utf-8'))
                jobs.append({k: j.get(k) for k in ('id', 'state', 'class', 'name', 'submitted', 'started', 'ended')})
            jobs.sort(key=lambda j: (str(j.get('submitted')), str(j.get('id'))))
            active = [j for j in jobs if j.get('state') in ('queued', 'running', 'cancel_requested')]
            shared = dict(active=active[:QUEUE_LIMIT], recent=[j for j in jobs if j not in active][-10:])
        except (OSError, ValueError) as exc:
            shared = dict(unavailable=str(exc)[:300])
    return dict(this_task=task_jobs, **({'shared_jobq': shared} if shared is not None else {}))


def _machine():
    state_file = os.environ.get('FACTORY_MACHINE_STATE')
    if not state_file:
        return None
    try:
        with open(state_file, encoding='utf-8') as handle:
            return json.load(handle)
    except (OSError, ValueError) as exc:
        return {'unavailable': str(exc)}


def _bound_in_run(host, task_id, graph, contracts, node_id):
    """Capsule id -> earlier nodes of this task that bound it, with how they ended."""
    from .scheduler import effective_contract
    used = {}
    for item in graph['nodes']:
        if item['node_id'] == node_id or not item.get('node_contract'):
            continue
        contract, needs_final = effective_contract(host, task_id, item, contracts)
        if needs_final or not contract:
            continue
        for cc in (contract.get('work') or {}).get('bound_ccs') or []:
            used.setdefault(cc, []).append(dict(
                node_id=item['node_id'], node_contract=item['node_contract'], state=item['state'],
                **({'outcome': item['outcome']} if item.get('outcome') else {}),
                **({'reason': item['reason']} if item.get('reason') else {})))
    return used


def _capsules(known, eligible, used, file_chars):
    out = {}
    for cc, entry in known.items():
        if eligible and cc not in eligible:
            continue
        try:
            item = capsule_view(cc, entry, file_chars)
        except Exception as exc:  # noqa: BLE001 - a broken capsule folder must not stop the brief
            item = dict(entry, unavailable=str(exc)[:300])
        item['used_in_this_run'] = used.get(cc, [])
        out[cc] = item
    return out


def finalize_brief(store, task_id, node_id):
    from .contract import load
    from .node_contract import node as contract_node_of
    from .node_finalize import draft_final, is_preliminary
    from .scheduler import _contracts, _graph, _resolve, catalog
    host = getattr(store, '_store', store)
    if hasattr(store, '_check'):
        store._check(task_id)
    task = host.get_task(task_id)
    graph = _graph(host, task_id)
    node = next((n for n in graph['nodes'] if n['node_id'] == node_id), None)
    if node is None:
        raise ValueError('Unknown plan node: ' + node_id)
    contracts = _contracts(host, task)
    prelim = contract_node_of(contracts, node.get('node_contract')) if contracts and node.get('node_contract') else None
    if not is_preliminary(prelim):
        raise ValueError(f'Node {node_id} has no preliminary node contract')
    try:
        contract = load(task['contract_id'])
    except (OSError, ValueError):
        contract = None
    plan, neighbours = _plan_view(host, task_id, graph, contracts, node_id, prelim)
    known = catalog()
    eligible = (prelim.get('work') or {}).get('eligible_ccs')
    used = _bound_in_run(host, task_id, graph, contracts, node_id)
    fixed = dict(schema='factory.finalize-brief/2', task_id=task_id, node_id=node_id, state=node['state'],
                 task=_task_view(task, contract, contracts), plan=plan, neighbours=neighbours,
                 briefing=prelim.get('briefing'), preliminary=prelim, draft_final=draft_final(prelim),
                 inputs=_resolve(host, task, prelim, graph['nodes']))
    direct = set(node.get('depends_on', []))
    for level, (file_chars, record_chars, other_chars) in enumerate(LEVELS):
        history = _history(host, task_id, graph, node, prelim, record_chars)
        brief = dict(
            fixed, upstream=_upstream(host, task_id, graph, contracts, direct, (record_chars, other_chars)),
            history=history, machine=dict(state=_machine(), queue=_queue(host, task_id)),
            capsules=_capsules(known, eligible, used, file_chars),
            bounds=dict(file_chars=file_chars, record_chars=record_chars, other_node_record_chars=other_chars,
                        brief_chars=BRIEF_CHARS,
                        **({'trimmed': f'Bounds tightened {level} step(s) to keep the brief under {BRIEF_CHARS} '
                                       'characters; cut items say how to read them whole.'} if level else {})),
            reading='factory.scheduler.capsule {"id", "path"?, "offset"?} reads any capsule file; '
                    'factory.scheduler.evidence {"id", "offset"?} reads any record of this task in full.',
            rule='The final contract may be more concrete or stricter than the preliminary one, never weaker. '
                 'Fill every slot, keep every criterion word for word, keep limits at or under the ceiling, '
                 'bind capsules in work.bound_ccs. If the preliminary contract cannot be met as written, do not '
                 'propose; report it as a spec gap.',
            # Kept at the top level as in brief 1: refusals of this node, earlier finals and failures of this node
            # contract, operator inputs, constraints and resources.
            refusals=[dict(problems=r['problems'], rationale=r['rationale'], by=r['by'])
                      for r in history['refusals'] if r['node_id'] == node_id],
            failures=history['this_node']['failures'],
            earlier_finals=[{k: f[k] for k in ('node_id', 'digest', 'diff', 'rationale')}
                            for f in history['this_node']['earlier_finals']],
            operator_inputs=history['operator']['inputs'],
            constraints=task.get('constraints'), resources=task.get('resources') or {})
        if _size(brief) <= BRIEF_CHARS:
            break
    return brief
