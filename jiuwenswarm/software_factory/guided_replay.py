"""Package pinned source and an existing construction run for the host replay."""
import argparse
import base64
import gzip
import hashlib
import io
import json
from pathlib import Path
import zipfile

from .workflow_library import WorkflowLibrary


SCHEMA = 'factory.guided-replay.v1'
PACKAGED_REPLAY = Path(__file__).with_name('data') / 'guided-replay.json.gz'


def read(path):
    return json.loads(path.read_bytes())


def read_evidence(run_dir, path):
    source = Path(path).resolve(strict=True)
    if not source.is_relative_to(run_dir):
        raise ValueError(f'Recording evidence must be inside the run directory: {source.name}')
    return source.read_bytes()


def public_task_graph(graph, composition):
    actions = {action['id']: action for action in composition['build_actions']}
    workflows = {workflow['id']: workflow['version'] for workflow in composition['library']}
    nodes = []
    for source in graph['nodes']:
        node = {key: value for key, value in source.items() if key not in {'workflow', 'subworkflow', 'origin'}}
        version = source['workflow']['version']
        action = actions.get(source['id'])
        if action:
            if version != action['version']:
                raise ValueError(f"Build action version mismatch: {source['id']}")
            node['step'] = {'kind': 'build_action', 'id': action['id'], 'version': version}
        else:
            project = source['workflow']['id']
            if workflows.get(project) != version:
                raise ValueError(f"Library workflow version mismatch: {source['id']}")
            node['step'] = {'kind': 'library_subworkflow', 'workflow': project,
                            'id': source['subworkflow'], 'version': version}
        nodes.append(node)
    return {**graph, 'schema': 'factory.task-graph.presentation.v1', 'nodes': nodes}


def scheduling_evidence(root, run_dir, graph, events):
    started = next((event for event in events if event['type'] == 'scheduler.started'), None)
    if started is None or 'graph_input' not in started['payload']:
        return None
    receipt = started['payload']['graph_input']
    filename = receipt['filename']
    if filename not in {'task_graph.json', 'graph.json'}:
        raise ValueError('Unexpected Scheduler input filename')
    directory = root.resolve(strict=True) if filename == 'task_graph.json' else run_dir
    saved = read_evidence(directory, directory / filename)
    sha256 = hashlib.sha256(saved).hexdigest()
    if sha256 != receipt['sha256'] or json.loads(saved) != graph:
        raise ValueError('Scheduler input differs from the admitted Task Graph')

    validated = next((event for event in events if event['type'] == 'graph.validated'), None)
    if (validated is None or validated['sequence'] >= started['sequence']
            or validated['payload']['graph'] != graph):
        raise ValueError('Scheduler started without validation of the input graph')
    return {
        'graphFile': {'name': filename, 'sha256': sha256, 'content': saved.decode('utf-8')},
        'validation': {'checks': validated['payload']['checks']},
    }


def build_guided_replay(root, run_dir, catalog_path, compose_path):
    run_dir = run_dir.resolve(strict=True)
    run = read(run_dir / 'run.json')
    event_bytes = (run_dir / 'events.jsonl').read_bytes()
    events = [json.loads(line) for line in event_bytes.splitlines()]
    if (run['status'] != 'verified' or not events or events[-1]['type'] != 'run.verified'
            or [event['sequence'] for event in events] != list(range(1, run['sequence'] + 1))):
        raise ValueError('Expected a complete recorded run')
    composition = read(compose_path)
    if (composition['construction_run'] != run['id'] or composition['graph'] != run['graph']
            or composition['task'] != run['graph']['task_contract']):
        raise ValueError('The Compose replay must produce the recorded construction graph from the same task')
    graph = public_task_graph(composition.pop('graph'), composition)
    workflows = []
    for ref in composition['library']:
        relative = Path('definitions') / ref['id'] / ref['version'].split(':')[1] / 'workflow.json'
        paths = [root / name / relative for name in ('imported-workflows', 'library')]
        path = next((candidate for candidate in paths if candidate.is_file()), None)
        if path is None:
            raise ValueError(f"Missing pinned workflow: {ref['id']}")
        workflow = WorkflowLibrary(path.parents[3]).get(ref['id'], ref['version'])
        if workflow['name'] != ref['name']:
            raise ValueError(f"Workflow name mismatch: {ref['id']}")
        workflows.append({
            'id': workflow['id'],
            'version': workflow['version'],
            'name': workflow['name'],
            'source': {key: workflow['source'][key] for key in ('repository', 'revision')},
            'subworkflows': [
                {key: part[key] for key in ('id', 'name', 'inputs', 'outputs')}
                for part in workflow['subworkflows']
            ],
        })
    source = run['outputs'].get('strata.source')
    if source is None:
        # A compute-only request still generates a verified source project as
        # an intermediate. Use that actual node output for the Product viewer.
        matches = [artifact for artifact in run['artifacts'] if artifact['kind'] == 'strata.source']
        if len(matches) != 1:
            raise ValueError('Expected one verified source archive in the run')
        source, = matches
    archive = read_evidence(run_dir, source['path'])
    if hashlib.sha256(archive).hexdigest() != source['sha256']:
        raise ValueError('Published source archive changed')
    with zipfile.ZipFile(io.BytesIO(archive)) as package:
        files = {entry.filename: package.read(entry).decode('utf-8')
                 for entry in package.infolist() if not entry.is_dir()}
        comparisons = {record['generated_path']: record for record in
                       json.loads(package.read('code_diff.json'))['files']
                       if record['generated_path'] in files and record.get('target') == 'ASCEND'}
    commands = []
    for event in events:
        if event['type'] == 'command.finished':
            command = event['payload']['command']
            logs = [read_evidence(run_dir, command[key]).decode('utf-8') for key in ('stdout_path', 'stderr_path')]
            commands.append({'node': event['node_id'], 'sequence': event['sequence'],
                             'argv': command['argv'], 'exit': command['exit_code'],
                             'output': '\n'.join(logs).strip()})
    # Keep only the output metadata needed to navigate this saved run.
    details = {'operations.selected', 'operation.result', 'aggregation.input_ready',
               'scheduler.started', 'scheduler.assignments_ready', 'scheduler.dispatched', 'scheduler.finished'}
    changes = details | {'node.started', 'node.verified', 'run.verified'}
    replay = []
    for event in events:
        kind = event['type']
        if kind not in changes:
            continue
        payload = event['payload'] if kind in details else {}
        if kind == 'node.verified':
            payload = {'outputs': {
                port: {'name': Path(output['path']).name, 'kind': output['kind']}
                for port, output in event['payload']['node']['outputs'].items()
            }}
        replay.append({'type': kind, 'node': event['node_id'],
                       'sequence': event['sequence'], 'payload': payload})
    data = {'schema': SCHEMA, 'workflows': workflows, 'graph': graph, 'composition': composition,
            'commands': commands, 'files': files,
            'comparisons': comparisons, 'projectName': Path(source['path']).stem,
            'archive': base64.b64encode(archive).decode(),
            'events': replay}
    scheduling = scheduling_evidence(root, run_dir, run['graph'], events)
    if scheduling is not None:
        data['scheduling'] = scheduling
    data['catalog'] = [
        {key: project[key] for key in ('id', 'name', 'repository', 'revision', 'groups', 'decomposition')}
        for project in read(catalog_path)
    ]
    expected_sources = [(item['id'], item['source']['revision']) for item in workflows]
    if [(item['id'], item['revision']) for item in data['catalog']] != expected_sources:
        raise ValueError('Catalog projects must match the recorded imports and pinned revisions')
    data['provenance'] = {
        'runId': run['id'],
        'finishedAt': run['finished_at'],
        'eventSha256': hashlib.sha256(event_bytes).hexdigest(),
        'archiveSha256': source['sha256'],
    }
    return data


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('workspace', 'run', 'output'):
        parser.add_argument('--' + name, required=True, type=Path)
    parser.add_argument('--catalog', required=True, type=Path)
    parser.add_argument('--compose-replay', required=True, type=Path)
    args = parser.parse_args()
    replay = build_guided_replay(args.workspace, args.run, args.catalog, args.compose_replay)
    payload = json.dumps(replay, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    temporary = args.output.with_suffix('.tmp')
    temporary.write_bytes(gzip.compress(payload, mtime=0))
    temporary.replace(args.output)
