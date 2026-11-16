"""Seal selected existing CC packages and write a task workflow configuration."""
import argparse
from dataclasses import asdict
import json
from pathlib import Path

from jiuwenswarm.ccv2.ccv2 import Host
from .cc_catalog import describe_capabilities
from .workflow_definitions import Binding, StageRef, SubworkflowDefinition, SubworkflowRef, WorkflowDefinition


def prepare(destination, task_id, packages, grants=()):
    destination = Path(destination).resolve()
    if destination.exists():
        raise ValueError('Configuration already exists; edit a reviewed revision explicitly')
    host = Host(destination.parent / 'ccstore', session_grants=grants)
    releases = [host.seal(Path(package).resolve()) for package in packages]
    caps = describe_capabilities(host, releases)
    subs, workflows = [], []
    for cap in caps:
        # The orchestration owner may subsequently compose these reusable leaves.
        # Optional capability ports stay optional; the full schema remains CC-owned.
        identifier = cap.id.replace('.', '-').replace(':', '-')
        inputs = {name: kind for name, kind in cap.inputs.items() if name not in cap.optional_inputs}
        bindings = {name: Binding('$input', name) for name in inputs}
        sub = SubworkflowDefinition(identifier, cap.name, inputs,
            (StageRef('call', cap.id, bindings),), {name: Binding('call', name) for name in cap.outputs})
        flow = WorkflowDefinition(identifier, cap.name, inputs,
            (SubworkflowRef('operation', identifier, bindings),), {name: Binding('operation', name) for name in cap.outputs})
        subs.append(asdict(sub))
        workflows.append(asdict(flow))
    result = dict(schema='factory.cc-workflows/1', task_id=task_id, root='workflows', cc_store='ccstore',
        releases=releases, grants=list(grants), max_nodes=128, subworkflows=subs, workflows=workflows)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--task-id', required=True)
    parser.add_argument('--package', action='append', required=True)
    parser.add_argument('--grant', action='append', default=[])
    args = parser.parse_args()
    result = prepare(args.config, args.task_id, args.package, args.grant)
    print(json.dumps({'config': str(args.config.resolve()), 'releases': result['releases']}, indent=2))


if __name__ == '__main__':
    main()
