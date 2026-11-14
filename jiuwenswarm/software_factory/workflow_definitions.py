"""Executable parent compositions over the real stage catalog.

Definitions bind typed ports. Expanding a parent includes its children; selecting
an internal stage exposes its inputs and does not replay its parent. The engine
executes these stage instances with its existing command/artifact machinery.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
import re
from typing import Mapping, Sequence

from .contracts import Stage, StageFailure


@dataclass(frozen=True)
class Binding:
    source: str  # A preceding local alias, or "$input".
    port: str


@dataclass(frozen=True)
class StageRef:
    id: str
    stage_id: str
    bindings: Mapping[str, Binding] = field(default_factory=dict)


@dataclass(frozen=True)
class SubworkflowDefinition:
    id: str
    name: str
    inputs: Mapping[str, str]
    stages: tuple[StageRef, ...]
    outputs: Mapping[str, Binding]


@dataclass(frozen=True)
class SubworkflowRef:
    id: str
    definition: str
    bindings: Mapping[str, Binding] = field(default_factory=dict)


@dataclass(frozen=True)
class WorkflowDefinition:
    id: str
    name: str
    inputs: Mapping[str, str]
    subworkflows: tuple[SubworkflowRef, ...]
    outputs: Mapping[str, Binding]


@dataclass(frozen=True)
class PortReference:
    node_id: str | None
    port: str
    kind: str

    def serializable(self):
        return asdict(self)


@dataclass(frozen=True)
class StageInstance:
    id: str
    stage_id: str
    input_bindings: Mapping[str, PortReference]
    workflow_path: str

    def serializable(self):
        return {'id': self.id, 'stage_id': self.stage_id, 'workflow_path': self.workflow_path,
                'input_bindings': {name: value.serializable() for name, value in self.input_bindings.items()}}


@dataclass(frozen=True)
class ExpandedGraph:
    path: str
    instance_id: str
    inputs: Mapping[str, str]
    nodes: tuple[StageInstance, ...]
    outputs: Mapping[str, PortReference]

    @property
    def edges(self):
        return [{'from': ref.node_id, 'to': node.id, 'data': ref.kind,
                 'source_port': ref.port, 'target_port': name}
                for node in self.nodes for name, ref in node.input_bindings.items()
                if ref.node_id is not None]

    def bind_inputs(self, bindings: Mapping[str, PortReference]):
        """Wire selected phases together; type mismatches cannot rename artifacts."""
        for name, ref in bindings.items():
            if not isinstance(ref, PortReference) or ref.node_id is None or name not in self.inputs or ref.kind != self.inputs[name]:
                raise StageFailure('workflow_contract_mismatch', f'Invalid binding for {self.path}.{name}')
        def bound(ref):
            return bindings.get(ref.port, ref) if ref.node_id is None else ref
        nodes = tuple(replace(node, input_bindings={name: bound(ref) for name, ref in node.input_bindings.items()})
                      for node in self.nodes)
        return replace(self, inputs={name: kind for name, kind in self.inputs.items() if name not in bindings},
                       nodes=nodes, outputs={name: bound(ref) for name, ref in self.outputs.items()})

    def serializable(self):
        return {'path': self.path, 'instance_id': self.instance_id, 'inputs': dict(self.inputs),
                'nodes': [node.serializable() for node in self.nodes], 'edges': self.edges,
                'outputs': {name: ref.serializable() for name, ref in self.outputs.items()}}


def _identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r'[a-zA-Z0-9_-]+', value):
        raise StageFailure('invalid_workflow_definition', f'Invalid local identifier {value!r}')


class WorkflowRegistry:
    def __init__(self, stages: Sequence[Stage], subworkflows=None, workflows=None):
        self.stages = {stage.id: stage for stage in stages}
        if len(self.stages) != len(stages):
            raise StageFailure('invalid_workflow_definition', 'Duplicate executable stage ID')
        for stage in stages:
            if not callable(stage.execute):
                raise StageFailure('invalid_workflow_definition', f'No callable for {stage.id}')
            if not stage.outputs or any(not isinstance(kind, str) or not kind for kind in (*stage.inputs.values(), *stage.outputs.values())):
                raise StageFailure('invalid_workflow_definition', f'Invalid contracts for {stage.id}')
        if subworkflows is None and workflows is None:
            subworkflows, workflows = default_definitions(self.stages)
        self.subworkflows = self._unique(subworkflows or (), 'subworkflow')
        self.workflows = self._unique(workflows or (), 'workflow')
        for definition in self.subworkflows.values():
            if not definition.stages:
                raise StageFailure('invalid_workflow_definition', f'Empty subworkflow {definition.id}')
            self._expand_subworkflow(definition, 'validation/' + definition.id,
                                     {name: PortReference(None, name, kind) for name, kind in definition.inputs.items()})
        for definition in self.workflows.values():
            if not definition.subworkflows:
                raise StageFailure('invalid_workflow_definition', f'Empty workflow {definition.id}')
            self.expand(definition.id, instance_id='validation')

    @staticmethod
    def _unique(definitions, kind):
        records = {}
        for value in definitions:
            _identifier(value.id)
            if value.id in records:
                raise StageFailure('invalid_workflow_definition', f'Duplicate {kind} {value.id}')
            records[value.id] = value
        return records

    @staticmethod
    def _resolve(binding: Binding, available):
        if not isinstance(binding, Binding) or binding.source not in available or binding.port not in available[binding.source]:
            raise StageFailure('invalid_workflow_definition', f'Unknown or forward port binding {binding!r}')
        return available[binding.source][binding.port]

    def _bindings(self, required, declarations, available):
        if set(required) != set(declarations):
            raise StageFailure('invalid_workflow_definition', f'Expected bound input ports {sorted(required)}, received {sorted(declarations)}')
        resolved = {name: self._resolve(binding, available) for name, binding in declarations.items()}
        for name, ref in resolved.items():
            if ref.kind != required[name]:
                raise StageFailure('workflow_contract_mismatch', f'{name}: {ref.kind} cannot supply {required[name]}')
        return resolved

    def _expand_subworkflow(self, definition, prefix, inputs):
        available = {'$input': inputs}
        nodes = []
        for step in definition.stages:
            _identifier(step.id)
            if step.id in available:
                raise StageFailure('invalid_workflow_definition', f'Duplicate local phase {step.id}')
            stage = self.stages.get(step.stage_id)
            if stage is None:
                raise StageFailure('invalid_workflow_definition', f'Unknown executable stage {step.stage_id}')
            bindings = self._bindings(stage.inputs, step.bindings, available)
            instance = StageInstance(prefix + '/' + step.id, stage.id, bindings, prefix.split('/', 1)[-1] + '/' + step.id)
            nodes.append(instance)
            available[step.id] = {name: PortReference(instance.id, name, kind) for name, kind in stage.outputs.items()}
        if not definition.outputs:
            raise StageFailure('invalid_workflow_definition', f'No outputs in {definition.id}')
        outputs = {name: self._resolve(binding, available) for name, binding in definition.outputs.items()}
        return nodes, outputs

    def expand(self, path: str, instance_id='main') -> ExpandedGraph:
        _identifier(instance_id)
        segments = path.split('/')
        if not 1 <= len(segments) <= 3 or segments[0] not in self.workflows:
            raise StageFailure('unknown_workflow', f'Unknown workflow path {path!r}')
        workflow = self.workflows[segments[0]]
        prefix = instance_id + '/' + workflow.id
        if len(segments) > 1:
            reference = next((step for step in workflow.subworkflows if step.id == segments[1]), None)
            if reference is None or reference.definition not in self.subworkflows:
                raise StageFailure('unknown_workflow', f'Unknown subworkflow path {path!r}')
            definition = self.subworkflows[reference.definition]
            prefix += '/' + reference.id
            if len(segments) == 3:
                step = next((step for step in definition.stages if step.id == segments[2]), None)
                if step is None:
                    raise StageFailure('unknown_workflow', f'Unknown stage path {path!r}')
                stage = self.stages[step.stage_id]
                inputs = {name: PortReference(None, name, kind) for name, kind in stage.inputs.items()}
                instance = StageInstance(prefix + '/' + step.id, stage.id, inputs, path)
                outputs = {name: PortReference(instance.id, name, kind) for name, kind in stage.outputs.items()}
                return ExpandedGraph(path, instance_id, stage.inputs, (instance,), outputs)
            inputs = {name: PortReference(None, name, kind) for name, kind in definition.inputs.items()}
            nodes, outputs = self._expand_subworkflow(definition, prefix, inputs)
            return ExpandedGraph(path, instance_id, definition.inputs, tuple(nodes), outputs)
        available = {'$input': {name: PortReference(None, name, kind) for name, kind in workflow.inputs.items()}}
        nodes = []
        for reference in workflow.subworkflows:
            _identifier(reference.id)
            if reference.id in available or reference.definition not in self.subworkflows:
                raise StageFailure('invalid_workflow_definition', f'Unknown/duplicate child {reference.id}')
            definition = self.subworkflows[reference.definition]
            inputs = self._bindings(definition.inputs, reference.bindings, available)
            children, outputs = self._expand_subworkflow(definition, prefix + '/' + reference.id, inputs)
            nodes.extend(children)
            available[reference.id] = outputs
        if not workflow.outputs:
            raise StageFailure('invalid_workflow_definition', f'No outputs in {workflow.id}')
        outputs = {name: self._resolve(binding, available) for name, binding in workflow.outputs.items()}
        return ExpandedGraph(path, instance_id, workflow.inputs, tuple(nodes), outputs)

    def export_stage_refs(self):
        result = []
        for workflow in self.workflows.values():
            for reference in workflow.subworkflows:
                definition = self.subworkflows[reference.definition]
                for step in definition.stages:
                    stage = self.stages[step.stage_id]
                    result.append({'path': '/'.join((workflow.id, reference.id, step.id)),
                                   'stage_id': stage.id, 'entrypoint': stage.serializable()['entrypoint'],
                                   'inputs': dict(stage.inputs), 'outputs': dict(stage.outputs)})
        return result

    def export(self):
        return {'workflows': [asdict(value) for value in self.workflows.values()],
                'subworkflows': [asdict(value) for value in self.subworkflows.values()],
                'stage_refs': self.export_stage_refs()}


def default_definitions(stages: Mapping[str, Stage]):
    """Declared runnable parents; missing optional families are simply unavailable."""
    subs = []
    workflows = []

    def leaf(identifier, stage_id, alias):
        stage = stages[stage_id]
        definition = SubworkflowDefinition(identifier, stage.name, dict(stage.inputs),
            (StageRef(alias, stage_id, {name: Binding('$input', name) for name in stage.inputs}),),
            {name: Binding(alias, name) for name in stage.outputs})
        subs.append(definition)
        return definition

    # Each sequence explicitly names real stage entrypoints. Cross-family inputs
    # remain visible typed inputs rather than invented implicit products.
    families = [
        ('source_acquisition', 'Source acquisition', [('repository_fetch', 'source.fetch', 'fetch'), ('cuda_analysis', 'source.cuda_ast', 'scan'), ('semantic_discovery', 'source.discover', 'discover')]),
        ('task_preparation', 'Engineering requirements', [('requirements', 'task.compile', 'compile')]),
        ('transformation', 'Semantic transformation', [('implementation_composition', 'metadata.compose_core', 'compose')]),
        ('function_extraction', 'Source function extraction', [('function_extraction', 'source.bind_operation', 'extract')]),
        ('scalar_implementation', 'Scalar source implementation', [('scalar_lowering', 'lower.scalar', 'lower')]),
        ('cooperative_implementation', 'Cooperative source implementation', [('cooperative_lowering', 'lower.cooperative', 'lower')]),
        ('construction', 'STRATA core construction', [('operator_mapping', 'construction.ascend_mapper', 'map'), ('source_generation', 'construction.codegen', 'generate'), ('cpp_build', 'construction.build', 'compile')]),
        ('verification', 'Core verification', [('core_validation', 'construction.execute', 'execute')]),
        ('delivery', 'Source delivery', [('source_packaging', 'construction.package', 'package'), ('source_portability', 'construction.rebuild_package', 'rebuild')]),
        ('engineering', 'Native component engineering', [('source_analysis', 'source.inspect', 'inspect'), ('backend_implementation', 'strata.implement', 'implement'), ('native_build', 'strata.build_components', 'compile')]),
        ('baseline', 'Original model evaluation', [('original_build', 'strata.baseline_build', 'compile'), ('original_inference', 'strata.baseline_inference', 'infer')]),
        ('execution', 'Candidate model execution', [('full_engine_build', 'strata.build_full', 'compile'), ('model_inference', 'strata.inference', 'infer')]),
        ('model_evaluation', 'Model comparison', [('inference_comparison', 'strata.compare', 'compare')]),
        ('environment_validation', 'Environment inspection', [('environment_validation', 'environment.inspect', 'inspect')]),
        ('environment_repair', 'Toolchain installation', [('dependency_recovery', 'toolchain.install', 'install')]),
        ('assessment', 'Observed factory assessment', [('value_analysis', 'value.assess', 'assess')]),
    ]
    for workflow_id, name, members in families:
        if not all(stage_id in stages for _, stage_id, _ in members):
            continue
        inputs = {}
        producers = {}
        references = []
        outputs = {}
        for sub_id, stage_id, alias in members:
            definition = leaf(workflow_id + '-' + sub_id, stage_id, alias)
            bindings = {}
            for port, kind in definition.inputs.items():
                if kind in producers:
                    bindings[port] = producers[kind]
                else:
                    # Distinct names for externally supplied ports of same name
                    # but different contracts; no schema renaming is performed.
                    external = port
                    if external in inputs and inputs[external] != kind:
                        external = sub_id + '_' + port
                    inputs[external] = kind
                    bindings[port] = Binding('$input', external)
            references.append(SubworkflowRef(sub_id, definition.id, bindings))
            for port, kind in stages[stage_id].outputs.items():
                producers[kind] = Binding(sub_id, port)
                key = port if port not in outputs else sub_id + '_' + port
                outputs[key] = Binding(sub_id, port)
        workflows.append(WorkflowDefinition(workflow_id, name, inputs, tuple(references), outputs))
    return subs, workflows


def execute_workflow_selection(ctx, inputs):
    path = ctx.options.get('workflow_path')
    if not isinstance(path, str) or not path:
        raise StageFailure('invalid_workflow_selection', 'Specify a registered workflow_path')
    outputs = ctx.execution.import_workflow(path, instance_id=ctx.node['id'],
                                            parameters=ctx.options.get('workflow_parameters') or {})
    return {'execution': ctx.write_json('workflow-execution.json', {
        'schema': 'factory.workflow.execution.v1', 'path': path,
        'outputs': {name: artifact.serializable() for name, artifact in outputs.items()}})}


def workflow_stages():
    return [Stage('workflow.execute', 'Execute a registered workflow selection', 'workflow_execution', 'nested_execution',
                  {}, {'execution': 'workflow.execution'}, execute_workflow_selection)]
