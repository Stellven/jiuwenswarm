"""Operator-configured native workflow service. Requests never select authority."""
import json
import os
from pathlib import Path

from jiuwenswarm.ccv2.ccv2 import Host
from .cc_catalog import describe_capabilities
from .cc_workflow import CCWorkflow
from .interconnect import contract_schema
from .workflow_definitions import (
    Binding, PortReference, StageRef, SubworkflowRef, SubworkflowDefinition, WorkflowDefinition, WorkflowRegistry,
)


def binding_map(value):
    result={}
    for name,ref in value.items():
        ref=dict(ref)
        if 'node' in ref:
            if 'source' in ref and ref['source'] != ref['node']:
                raise ValueError('Conflicting common and legacy binding aliases')
            ref['source']=ref.pop('node')
        result[name]=Binding(**ref)
    return result


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
            max_nodes=config.get('max_nodes', 128), deadline=config.get('deadline'), context={'environment':context},
            interconnect=config.get('interconnect'))
        return cls(runtime, definitions(config, caps))

    def catalog(self):
        return dict(task_id=self.runtime.task_id, capabilities=[c.serializable(include_contracts=self.runtime.interconnect is not None)
                                                                     for c in self.runtime.capabilities.values()],
                    interconnect=self.runtime.interconnect,
                    **({'interconnect_schema': contract_schema()} if self.runtime.interconnect else {}),
                    **self.registry.export(),
                    shared_pool=self.shared_pool())

    def shared_pool(self):
        from .shared_catalog import export_pool
        return export_pool(self)

    def _capture(self, run):
        result = dict(run)
        result['scopes'] = self.scopes(run)
        return result

    @staticmethod
    def scopes(run):
        groups = {}
        for node in run['nodes']:
            segments = node['id'].split('/')
            for depth in range(2,len(segments)):
                groups.setdefault('/'.join(segments[:depth]),[]).append(node)
        result=[]
        for path,nodes in groups.items():
            states={n['state'] for n in nodes}
            status='completed' if states=={'completed'} else 'failed' if states & {'failed','blocked'} else 'cancelled' if states=={'cancelled'} else 'active'
            result.append(dict(path=path,status=status,children=[n['id'] for n in nodes]))
        return result

    def get(self, run_id):
        run=self.runtime.get(run_id)
        return {**run,'scopes':self.scopes(run)}

    def tick(self, run_id):
        return self._capture(self.runtime.tick(run_id))

    def stop(self, run_id):
        return self._capture(self.runtime.stop(run_id))

    def create(self, request):
        allowed = {'workflow', 'inputs', 'objective', 'run_id', 'definitions'}
        if set(request) - allowed:
            raise ValueError('Unknown workflow request fields')
        registry = definitions(request['definitions'], list(self.runtime.capabilities.values())) if 'definitions' in request else self.registry
        return self._capture(self.runtime.create(registry.expand(request['workflow']), request.get('inputs', {}),
            objective=request['objective'], run_id=request.get('run_id')))

    def append(self, run_id, request):
        # A new instance namespace prevents accidental overwrites. Registry
        # definitions may be composed dynamically by the orchestration owner;
        # every leaf still has to exist in the operator-selected CC catalog.
        registry = definitions(request['definitions'], list(self.runtime.capabilities.values())) if 'definitions' in request else self.registry
        graph = registry.expand(request['workflow'], instance_id=request['instance_id'])
        if request.get('bindings'):
            graph = graph.bind_inputs({name: PortReference(**({**{k:v for k,v in value.items() if k != 'node'},
                'node_id':value['node']} if 'node' in value else value)) for name, value in request['bindings'].items()})
        return self._capture(self.runtime.append(run_id, graph, request.get('inputs', {}),
            expected_revision=request['expected_revision'], decision=request['decision']))
