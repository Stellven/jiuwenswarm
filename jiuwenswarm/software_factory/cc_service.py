"""Operator-configured native workflow service. Requests never select authority."""
import json
import os
from pathlib import Path

from jiuwenswarm.ccv2.ccv2 import Host
from .cc_catalog import describe_capabilities
from .cc_workflow import CCWorkflow
from .workflow_definitions import (
    Binding, PortReference, StageRef, SubworkflowRef, SubworkflowDefinition, WorkflowDefinition, WorkflowRegistry,
)


def binding_map(value):
    return {name: Binding(**ref) for name, ref in value.items()}


def definitions(value, capabilities):
    subs = []
    for item in value.get('subworkflows', []):
        steps = []
        for step in item['stages']:
            cls = SubworkflowRef if 'definition' in step else StageRef
            steps.append(cls(**{**step, 'bindings': binding_map(step.get('bindings', {}))}))
        subs.append(SubworkflowDefinition(item['id'], item['name'], item['inputs'], tuple(steps), binding_map(item['outputs'])))
    workflows = [WorkflowDefinition(item['id'], item['name'], item['inputs'],
        tuple(SubworkflowRef(**{**ref, 'bindings': binding_map(ref.get('bindings', {}))}) for ref in item['subworkflows']),
        binding_map(item['outputs'])) for item in value.get('workflows', [])]
    return WorkflowRegistry(capabilities, subs, workflows)


class CCService:
    def __init__(self, runtime, registry):
        self.runtime, self.registry = runtime, registry

    @classmethod
    def from_config(cls, path):
        path = Path(path).resolve()
        config = json.loads(path.read_text(encoding='utf-8'))
        if config.get('schema') != 'factory.cc-workflows/1':
            raise ValueError('Expected factory.cc-workflows/1 operator configuration')
        base = path.parent
        resolve = lambda p: str((base / p).resolve())
        # One service process per task. No request-scoped os.environ mutation,
        # so concurrent requests cannot execute under another task's authority.
        context = {key: os.environ.get(key, '') for key in (
            'FACTORY_TASK_ID', 'FACTORY_HOME', 'FACTORY_WORKSPACE', 'FACTORY_READ_TASKS',
            'FACTORY_PYTHON', 'FACTORY_BRIDGE_DIR', 'SIMINFENG_ROOT', 'PYTHONPATH')}
        task_id = config['task_id']
        grants = config.get('grants', [])
        host = Host(resolve(config['cc_store']), session_grants=grants)
        # Release digests are prepared explicitly; restarting never reseals
        # mutable source directories into a different executable identity.
        caps = describe_capabilities(host, config['releases'])
        if any(c.id.startswith('factory.') for c in caps):
            if context['FACTORY_TASK_ID'] != task_id or not context['FACTORY_HOME']:
                raise ValueError('Factory capsules require the matching task-scoped process environment')
            from jiuwenswarm.factory.store import Store
            with Store(context['FACTORY_HOME']) as store:
                store.get_task(task_id)
        runtime = CCWorkflow(resolve(config['root']), host, caps, task_id=task_id, grants=grants,
            max_nodes=config.get('max_nodes', 128), deadline=config.get('deadline'), context={'environment': context})
        return cls(runtime, definitions(config, caps))

    def catalog(self):
        return dict(task_id=self.runtime.task_id, capabilities=[c.serializable() for c in self.runtime.capabilities.values()],
                    **self.registry.export())

    def create(self, request):
        allowed = {'workflow', 'inputs', 'objective', 'run_id', 'definitions'}
        if set(request) - allowed:
            raise ValueError('Unknown workflow request fields')
        registry = definitions(request['definitions'], list(self.runtime.capabilities.values())) if 'definitions' in request else self.registry
        return self.runtime.create(registry.expand(request['workflow']), request.get('inputs', {}),
            objective=request['objective'], run_id=request.get('run_id'))

    def append(self, run_id, request):
        # A new instance namespace prevents accidental overwrites. Registry
        # definitions may be composed dynamically by the orchestration owner;
        # every leaf still has to exist in the operator-selected CC catalog.
        registry = definitions(request['definitions'], list(self.runtime.capabilities.values())) if 'definitions' in request else self.registry
        graph = registry.expand(request['workflow'], instance_id=request['instance_id'])
        if request.get('bindings'):
            graph = graph.bind_inputs({name: PortReference(**value) for name, value in request['bindings'].items()})
        return self.runtime.append(run_id, graph, request.get('inputs', {}),
            expected_revision=request['expected_revision'], decision=request['decision'])
