"""Seal selected existing CC packages and write a task workflow configuration."""
import argparse
from dataclasses import asdict
import json
from pathlib import Path

from jiuwenswarm.ccv2.ccv2 import Host
from .cc_catalog import describe_capabilities
from .interconnect import VERSION
from .workflow_definitions import Binding, StageRef, SubworkflowDefinition, SubworkflowRef, WorkflowDefinition


def prepare(destination, task_id, packages, grants=(), *, interconnect=VERSION):
    if interconnect not in {None, VERSION}:
        raise ValueError('Unsupported interconnect version')
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
    by_id = {cap.id:cap for cap in caps}
    if {'factory.builder:submit','factory.throughput_campaign:submit'} <= set(by_id):
        build = SubworkflowDefinition('candidate-construction','Construct candidate',{'request':'json'},
            (StageRef('build','factory.builder:submit',{'request':Binding('$input','request')}),),
            {'build_attempt_id':Binding('build','attempt_id',channel='result')})
        screen = SubworkflowDefinition('candidate-screen','Screen candidate',{'build_attempt_id':'text'},
            (StageRef('screen','factory.throughput_campaign:submit',{'request':Binding('$input','build_attempt_id',
                assemble={'template':{'stage':'screen'},'at':'/build_attempt_id'})}),),
            {'comparison':Binding('screen','result',channel='result')})
        confirm = SubworkflowDefinition('candidate-confirm','Confirm unchanged candidate',{'build_attempt_id':'text'},
            (StageRef('confirm','factory.throughput_campaign:submit',{'request':Binding('$input','build_attempt_id',
                assemble={'template':{'stage':'confirm'},'at':'/build_attempt_id'})}),),
            {'comparison':Binding('confirm','result',channel='result')})
        cycle = SubworkflowDefinition('construct-and-evaluate','Construct and independently evaluate',{'build_request':'json'},
            (SubworkflowRef('construction','candidate-construction',{'request':Binding('$input','build_request')}),
             SubworkflowRef('evaluation','candidate-screen',{'build_attempt_id':Binding('construction','build_attempt_id')})),
            {'comparison':Binding('evaluation','comparison'),'build_attempt_id':Binding('construction','build_attempt_id')})
        subs.extend(asdict(item) for item in (build,screen,confirm,cycle))
        workflows.append(asdict(WorkflowDefinition('strata-candidate-cycle','STRATA candidate cycle',{'build_request':'json'},
            (SubworkflowRef('experiment','construct-and-evaluate',{'build_request':Binding('$input','build_request')}),),
            {'comparison':Binding('experiment','comparison'),'build_attempt_id':Binding('experiment','build_attempt_id')})))
        workflows.append(asdict(WorkflowDefinition('strata-independent-confirmation','STRATA confirmation',{'build_attempt_id':'text'},
            (SubworkflowRef('confirmation','candidate-confirm',{'build_attempt_id':Binding('$input','build_attempt_id')}),),
            {'comparison':Binding('confirmation','comparison')})))
    result = dict(schema='factory.cc-workflows/1', task_id=task_id, root='workflows', cc_store='ccstore',
        releases=releases, grants=list(grants), max_nodes=128, subworkflows=subs, workflows=workflows)
    if interconnect:
        result['interconnect'] = interconnect
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
