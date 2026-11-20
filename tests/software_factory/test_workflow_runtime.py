"""Actual file/process handoffs; Agent stand-ins are confined to this test file."""
import hashlib
import json
from pathlib import Path
import sys

import pytest

from jiuwenswarm.software_factory.workflow_runtime import WorkflowExecutor


class Library:
    def __init__(self, parts):
        self.parts = parts

    def resolve(self, workflow, version, subworkflow):
        assert version == 'pinned-1'
        return self.parts[(workflow, subworkflow)]


def contract(kind, **extra):
    return {'semantic_type': kind, **extra}


def part(entrypoint, inputs=None, outputs=None, **extra):
    return {'id': entrypoint, 'name': entrypoint, 'inputs': inputs or {}, 'outputs': outputs or {},
            'implementation': {'type': 'python', 'entrypoint': entrypoint}, **extra}


def node(identity, workflow, selected, bindings=None, **extra):
    return {'id': identity, 'workflow': {'id': workflow, 'version': 'pinned-1'},
            'subworkflow': selected, 'bindings': bindings or {}, **extra}


def artifact(path, kind='source.raw'):
    return {'id': 'external-source', 'kind': kind, 'path': str(path),
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'size': path.stat().st_size, 'producer': '$input'}


def test_cross_workflow_process_consumes_real_upstream_file(tmp_path):
    original = tmp_path / 'source.txt'
    original.write_text('expert weights')

    def transform(ctx, inputs, parameters):
        output = ctx.workspace / 'normalized.txt'
        ctx.run_command([sys.executable, '-c',
                         'from pathlib import Path;import sys;Path(sys.argv[2]).write_text(Path(sys.argv[1]).read_text().upper())',
                         inputs['raw']['path'], str(output)])
        return {'normalized': output}

    def consume(ctx, inputs, parameters):
        output = ctx.workspace / 'result.json'
        text = Path(inputs['data']['path']).read_text()
        assert text == 'EXPERT WEIGHTS'
        output.write_text(json.dumps({'consumed': text, 'revision': parameters['revision']}))
        return {'result': output}

    library = Library({('analysis', 'extract'): part('test:transform', {'raw': contract('source.raw')},
                                                   {'normalized': contract('source.normalized')},
                                                   requirements={'executables': ['python']}),
                       ('engineering', 'verify'): part('test:consume', {'data': contract('source.normalized')},
                                                       {'result': contract('verification.report', format='json')},
                                                       default_parameters={'revision': 'abc123'})})
    graph = {'inputs': {'source': artifact(original)},
             'nodes': [node('verify', 'engineering', 'verify', {'data': {'node': 'extract', 'port': 'normalized'}}),
                       node('extract', 'analysis', 'extract', {'raw': {'node': '$input', 'port': 'source'}})],
             'outputs': {'report': {'node': 'verify', 'port': 'result'}}}
    graph_file = tmp_path / 'planner-graph.json'
    graph_file.write_text(json.dumps(graph))
    observed = []
    snapshot = WorkflowExecutor(library, tmp_path / 'runs', handlers={'test:transform': transform, 'test:consume': consume}).run(
        graph_file, run_id='actual-process', emit=lambda kind, payload: observed.append((kind, payload)))
    assert snapshot['status'] == 'verified'
    assert json.loads(Path(snapshot['outputs']['report']['path']).read_text()) == {
        'consumed': 'EXPERT WEIGHTS', 'revision': 'abc123'}
    extraction, verification = (next(item for item in snapshot['nodes'] if item['id'] == key)
                                for key in ('extract', 'verify'))
    command = extraction['attempts'][0]['commands'][0]
    assert command['exit_code'] == 0
    assert Path(command['stdout_path']).is_file()
    assert Path(verification['attempts'][0]['inputs']['data']['path']).is_relative_to(Path(snapshot['run_dir']))
    assert snapshot['edges'][0]['status'] == 'verified'
    assert any(kind == 'command.started' for kind, _ in observed)
    dispatched = [(index, payload) for index, (kind, payload) in enumerate(observed) if kind == 'scheduler.dispatched']
    assert [payload['node_id'] for _, payload in dispatched] == ['extract', 'verify']
    assert all(payload['worker_type'] == 'python' and payload['builder'] == 'Python/tool builder'
               for _, payload in dispatched)
    assert dispatched[0][1]['dependencies'] == []
    assert dispatched[1][1]['dependencies'] == ['extract']
    assert dispatched[0][1]['entrypoint'] == 'test:transform'
    assert dispatched[0][1]['required_tools'] == ['python']
    assert 'registered Python operation' in dispatched[0][1]['execution_reason']
    producer_verified = next(index for index, (kind, payload) in enumerate(observed)
                             if kind == 'node.verified' and payload['node_id'] == 'extract')
    assert producer_verified < dispatched[1][0]
    assert observed[0][0] == 'graph.validated'
    assert observed[0][1]['checks'] == ['Pinned workflow versions', 'Input and output contracts', 'Dependency links']
    assert observed[1] == ('scheduler.started', {
        'node_count': 2,
        'graph_path': 'graph.json',
        'graph_input': {'filename': graph_file.name, 'sha256': hashlib.sha256(graph_file.read_bytes()).hexdigest()},
        'dependency_check': 'jiuwenswarm.research.binding.kahn_order',
        'dispatch_gate': 'jiuwenswarm.research.scheduler_dependencies.unaccepted_predecessors',
    })
    assert observed[2] == ('scheduler.assignments_ready', {'assignments': [dispatched[1][1], dispatched[0][1]]})
    assert observed[-2] == ('scheduler.finished', {'status': 'verified', 'dispatched': 2})
    persisted = json.loads((Path(snapshot['run_dir']) / 'run.json').read_text())
    assert persisted['outputs'] == snapshot['outputs']
    assert (Path(snapshot['run_dir']) / 'graph.json').read_bytes() == graph_file.read_bytes()


def test_malformed_graph_file_is_rejected_before_emitting_or_dispatching(tmp_path):
    graph_file = tmp_path / 'planner-graph.json'
    graph_file.write_text('{"nodes":')
    observed = []
    executor = WorkflowExecutor(Library({}), tmp_path / 'runs')
    with pytest.raises(json.JSONDecodeError):
        executor.run(graph_file, emit=lambda kind, payload: observed.append(kind))
    assert observed == []


@pytest.mark.parametrize('invalid', ['cycle', 'edges'])
def test_invalid_graph_file_is_rejected_before_scheduling(tmp_path, invalid):
    library = Library({
        ('work', 'source'): part('test:source', outputs={'out': contract('source.raw')}),
        ('work', 'consumer'): part('test:consumer', {'in': contract('source.raw')},
                                  {'out': contract('source.raw')}),
    })
    graph = {
        'nodes': [node('first', 'work', 'source'),
                  node('second', 'work', 'consumer', {'in': {'node': 'first', 'port': 'out'}})],
        'edges': [],
    }
    if invalid == 'cycle':
        graph['nodes'][1]['bindings']['in']['node'] = 'second'
    graph_file = tmp_path / 'planner-graph.json'
    graph_file.write_text(json.dumps(graph))
    observed = []
    snapshot = WorkflowExecutor(library, tmp_path / 'runs').run(
        graph_file, emit=lambda kind, payload: observed.append(kind))
    assert snapshot['status'] == 'failed'
    assert snapshot['error']['code'] == {'cycle': 'dependency_cycle', 'edges': 'invalid_edges'}[invalid]
    assert observed == ['run.failed']


def test_changed_published_file_fails_and_blocks_downstream(tmp_path):
    source = tmp_path / 'source.txt'
    source.write_text('before')
    original = artifact(source)
    source.write_text('after')
    called = []

    def operation(ctx, inputs, parameters):
        called.append(True)
        return {}

    lib = Library({('a', 'read'): part('test:read', {'source': contract('source.raw')}, {'out': contract('middle')}),
                   ('b', 'later'): part('test:later', {'source': contract('middle')})})
    graph = {'inputs': {'source': original}, 'nodes': [
        node('first', 'a', 'read', {'source': {'node': '$input', 'port': 'source'}}),
        node('second', 'b', 'later', {'source': {'node': 'first', 'port': 'out'}})]}
    events = []
    result = WorkflowExecutor(lib, tmp_path / 'runs', handlers={'test:read': operation, 'test:later': operation}).run(
        graph, emit=lambda kind, payload: events.append((kind, payload)))
    assert result['status'] == 'failed'
    assert [item['status'] for item in result['nodes']] == ['failed', 'blocked']
    assert result['nodes'][0]['error']['code'] == 'artifact_changed'
    assert not called
    assert [payload['node_id'] for kind, payload in events if kind == 'scheduler.dispatched'] == ['first']
    assert events[-2] == ('scheduler.finished', {'status': 'failed', 'dispatched': 1})


@pytest.mark.parametrize('bad_mode', ['outside', 'symlink', 'invalid_json'])
def test_output_must_be_owned_and_pass_declared_content_contract(tmp_path, bad_mode):
    outside = tmp_path / 'external.json'
    outside.write_text('{"ok": true}')

    def operation(ctx, inputs, parameters):
        output = ctx.workspace / 'output.json'
        if bad_mode == 'outside':
            return {'result': outside}
        if bad_mode == 'symlink':
            output.symlink_to(outside)
        else:
            output.write_text('{"ok": "not-a-boolean"}')
        return {'result': output}

    lib = Library({('a', 'write'): part('test:write', outputs={'result': contract('report', json_schema={
        'type': 'object', 'properties': {'ok': {'type': 'boolean'}}, 'required': ['ok']})})})
    result = WorkflowExecutor(lib, tmp_path / 'runs', handlers={'test:write': operation}).run(
        {'nodes': [node('writer', 'a', 'write')]})
    assert result['status'] == 'failed'
    assert result['artifacts'] == []
    assert result['nodes'][0]['error']['code'] in {'artifact_escape', 'invalid_artifact', 'contract_invalid'}


def test_agent_must_produce_actual_declared_file(tmp_path):
    prompt = tmp_path / 'instruction.md'
    prompt.write_text('Create the required source file.')
    definition = {'name': 'Agent code generation', 'inputs': {}, 'outputs': {'code': contract('source.cpp')},
                  'implementation': {'type': 'agent', 'prompt_path': str(prompt)}}

    class TestOnlyDriver:
        def run(self, prompt, workspace, **kwargs):
            return {'text': '{"outputs":{"code":"never-created.cpp"}}',
                    'invocation': {'driver': 'explicit-isolated-test'}}

    result = WorkflowExecutor(Library({('agent', 'generate'): definition}), tmp_path / 'runs',
                              driver=TestOnlyDriver()).run({'nodes': [node('agent', 'agent', 'generate')]})
    assert result['status'] == 'failed'
    assert result['nodes'][0]['error']['code'] == 'missing_artifact'
    assert not result['artifacts']


def test_agent_file_is_consumed_and_instruction_is_recorded(tmp_path):
    prompt = tmp_path / 'instruction.md'
    prompt.write_text('Write an actual arithmetic C++ implementation.')
    definition = {'name': 'Agent code generation', 'inputs': {}, 'outputs': {'code': contract('source.cpp')},
                  'implementation': {'type': 'agent', 'prompt_path': str(prompt)},
                  'requirements': {'executables': [], 'capabilities': ['configured agent', 'filesystem']}}

    class TestOnlyDriver:
        def run(self, received_prompt, workspace, **kwargs):
            assert 'Write an actual arithmetic C++ implementation.' in received_prompt
            (workspace / 'core.cpp').write_text('int expert_count(int x) { return x + 1; }\n')
            return {'text': '{"outputs":{"code":"core.cpp"}}',
                    'invocation': {'driver': 'explicit-isolated-test'}}

    result = WorkflowExecutor(Library({('agent', 'generate'): definition}), tmp_path / 'runs',
                              driver=TestOnlyDriver()).run({'nodes': [node('agent', 'agent', 'generate')]})
    assert result['status'] == 'verified'
    assert Path(result['artifacts'][0]['path']).read_text().startswith('int expert_count')
    events = [json.loads(line) for line in (Path(result['run_dir']) / 'events.jsonl').read_text().splitlines()]
    dispatch = next(event for event in events if event['type'] == 'scheduler.dispatched')
    event = next(event for event in events if event['type'] == 'agent.started')
    assert dispatch['payload'] == {
        'node_id': 'agent', 'worker_type': 'agent', 'builder': 'Agent builder', 'dependencies': [],
        'execution_reason': 'The pinned workflow uses a Markdown instruction executed by Codex.',
        'entrypoint': 'instruction.md',
    }
    assert dispatch['sequence'] < event['sequence']
    assert event['payload']['instruction_sha256'] == hashlib.sha256(prompt.read_bytes()).hexdigest()


def test_source_pin_cannot_be_changed_by_graph(tmp_path):
    lib = Library({('source', 'extract'): part('test:extract', default_parameters={'revision': 'immutable'})})
    result = WorkflowExecutor(lib, tmp_path / 'runs', handlers={}).run({
        'nodes': [node('extract', 'source', 'extract', parameters={'revision': 'attacker-version'})]})
    assert result['status'] == 'failed'
    assert result['nodes'][0]['error']['code'] == 'source_pin_changed'


def test_cycles_and_semantic_mismatch_fail_before_any_stage_runs(tmp_path):
    lib = Library({('a', 'work'): part('test:never', {'value': contract('same')}, {'value': contract('same')})})
    graph = {'nodes': [node('n1', 'a', 'work', {'value': {'node': 'n2', 'port': 'value'}}),
                       node('n2', 'a', 'work', {'value': {'node': 'n1', 'port': 'value'}})]}
    result = WorkflowExecutor(lib, tmp_path / 'runs', handlers={}).run(graph)
    assert result['error']['code'] == 'dependency_cycle'
    assert all(not item['attempts'] for item in result['nodes'])


def test_no_untrusted_python_import_from_graph(tmp_path):
    lib = Library({('unsafe', 'run'): part('os:system')})
    result = WorkflowExecutor(lib, tmp_path / 'runs').run({'nodes': [node('unsafe', 'unsafe', 'run')]})
    assert result['nodes'][0]['error']['code'] == 'untrusted_entrypoint'


def test_real_command_failure_retains_downloadable_streams(tmp_path):
    def fail(ctx, inputs, parameters):
        ctx.run_command([sys.executable, '-c',
                         'import sys;print("actual compile attempt");print("actual failure",file=sys.stderr);sys.exit(7)'])
        raise AssertionError('A failed command must not return success')

    lib = Library({('build', 'compile'): part('test:fail')})
    result = WorkflowExecutor(lib, tmp_path / 'runs', handlers={'test:fail': fail}).run({
        'nodes': [node('compile', 'build', 'compile')]})
    assert result['status'] == 'failed'
    command = result['nodes'][0]['attempts'][0]['commands'][0]
    assert command['exit_code'] == 7
    assert command['stdout'] == 'actual compile attempt\n'
    assert command['stderr'] == 'actual failure\n'
    assert Path(command['stdout_artifact']['path']).read_text() == command['stdout']
    assert Path(command['stderr_artifact']['path']).read_text() == command['stderr']
    assert {item['kind'] for item in result['artifacts']} == {'execution.stdout', 'execution.stderr'}


def test_semantic_type_mismatch_rejects_graph_before_execution(tmp_path):
    source = tmp_path / 'source.txt'
    source.write_text('actual source')
    lib = Library({('native', 'map'): part('test:never', {'source': contract('ascend.operators')})})
    result = WorkflowExecutor(lib, tmp_path / 'runs', handlers={}).run({
        'inputs': {'source': artifact(source, kind='cuda.operators')},
        'nodes': [node('map', 'native', 'map', {'source': {'node': '$input', 'port': 'source'}})]})
    assert result['error']['code'] == 'contract_mismatch'
    assert result['nodes'][0]['attempts'] == []


def test_artifact_id_is_unique_across_runs_and_input_identity_is_retained(tmp_path):
    def write(ctx, inputs, parameters):
        output = ctx.workspace / 'actual.cpp'
        output.write_text('int value() { return 7; }\n')
        return {'code': output}

    def consume(ctx, inputs, parameters):
        output = ctx.workspace / 'consumed.cpp'
        output.write_bytes(Path(inputs['code']['path']).read_bytes())
        return {'copy': output}

    library = Library({('source', 'write'): part('test:write', outputs={'code': contract('source.cpp')}),
                       ('consumer', 'read'): part('test:consume', inputs={'code': contract('source.cpp')},
                                                 outputs={'copy': contract('source.cpp')})})
    executor = WorkflowExecutor(library, tmp_path / 'runs', handlers={'test:write': write, 'test:consume': consume})
    graph = {'nodes': [node('write', 'source', 'write'),
                       node('consume', 'consumer', 'read', {'code': {'node': 'write', 'port': 'code'}})]}
    first, second = executor.run(graph, run_id='first'), executor.run(graph, run_id='second')
    assert {item['id'] for item in first['artifacts']}.isdisjoint({item['id'] for item in second['artifacts']})
    assert first['nodes'][1]['attempts'][0]['inputs']['code']['id'] == first['nodes'][0]['outputs']['code']['id']


def test_changed_pinned_agent_instruction_between_nodes_prevents_execution(tmp_path):
    from jiuwenswarm.software_factory.workflow_library import WorkflowLibrary

    library = WorkflowLibrary(tmp_path / 'library')
    original_prompt = Path(__file__).resolve().parents[2] / 'jiuwenswarm/software_factory/workflow_prompts/design_reference_tests.md'
    bundle = library.register({'id': 'construction', 'name': 'Construction', 'source': {}, 'subworkflows': [
        {'id': 'prepare', 'name': 'Prepare actual input', 'inputs': {}, 'outputs': {'report': contract('report')},
         'implementation': {'type': 'python', 'entrypoint': 'jiuwenswarm.software_factory.library_operations:report'}},
        {'id': 'agent', 'name': 'Execute pinned instruction', 'inputs': {'report': contract('report')},
         'outputs': {'tests': contract('source.tests')},
         'implementation': {'type': 'agent', 'prompt_path': str(original_prompt)}}]})
    pinned_prompt = Path(bundle['subworkflows'][1]['implementation']['prompt_path'])

    def prepare(ctx, inputs, parameters):
        output = ctx.workspace / 'report.txt'
        output.write_text('actual preceding-stage artifact\n')
        return {'report': output}

    class NeverCalledDriver:
        def run(self, *args, **kwargs):
            raise AssertionError('Changed pinned instructions must be rejected before a model call')

    def observe(kind, payload):
        if kind == 'node.verified' and payload['node_id'] == 'prepare':
            pinned_prompt.write_text('changed after the first node completed\n')

    nodes = [node('prepare', 'construction', 'prepare'),
             node('agent', 'construction', 'agent', {'report': {'node': 'prepare', 'port': 'report'}})]
    for item in nodes:
        item['workflow']['version'] = bundle['version']
    result = WorkflowExecutor(library, tmp_path / 'runs', driver=NeverCalledDriver(),
                              handlers={'jiuwenswarm.software_factory.library_operations:report': prepare}).run(
        {'nodes': nodes}, emit=observe)
    assert [item['status'] for item in result['nodes']] == ['verified', 'failed']
    assert result['nodes'][1]['error']['code'] == 'instruction_changed'
    assert not result['nodes'][1]['outputs']


def test_definition_changed_during_node_execution_cannot_publish_outputs(tmp_path):
    library = Library({('source', 'write'): part('test:write', outputs={'code': contract('source.cpp')})})

    def changed_during_execution(ctx, inputs, parameters):
        output = ctx.workspace / 'actual.cpp'
        output.write_text('int generated() { return 3; }\n')
        library.parts[('source', 'write')]['implementation']['implementation_sha256'] = 'changed'
        return {'code': output}

    result = WorkflowExecutor(library, tmp_path / 'runs', handlers={'test:write': changed_during_execution}).run({
        'nodes': [node('write', 'source', 'write')]})
    assert result['status'] == 'failed'
    assert result['nodes'][0]['error']['code'] == 'definition_changed'
    assert result['artifacts'] == []
