"""Workflow leaf contracts are descriptions of sealed CC v2 capabilities.

There is deliberately no executable Stage adapter. Only Host.call executes a
leaf; workflow composition remains independent of capability implementation.
"""
from dataclasses import dataclass, field

from jiuwenswarm.ccv2.ccv2 import port


@dataclass(frozen=True)
class Capability:
    id: str
    name: str
    release: str
    capability: str
    inputs: dict
    outputs: dict
    optional_inputs: frozenset = field(default_factory=frozenset)
    changes: tuple = ()
    lifecycle: dict = field(default_factory=dict)

    def serializable(self):
        return dict(id=self.id, name=self.name, release=self.release,
                    capability=self.capability, inputs=self.inputs, outputs=self.outputs,
                    optional_inputs=sorted(self.optional_inputs), changes=list(self.changes),
                    lifecycle=self.lifecycle,
                    entrypoint={'cc': '2', 'release': self.release, 'capability': self.capability})


def describe_capabilities(host, releases):
    """Explicit operator-selected releases, never mutable package-name lookup."""
    result = []
    for release in releases:
        declaration = host.describe(release)
        for name, spec in declaration['capabilities'].items():
            if 'serves' in spec:
                continue
            # The previous factory-loop controller remains a rollback entrypoint,
            # not a nested scheduler hidden inside a completed workflow leaf.
            if declaration['id'] == 'factory.engine_factory_loop' or (
                declaration['id'] in {'factory.inference_lab', 'factory.strata_throughput_workbench', 'factory.strata_prefill_workbench'}
                and name in {'select', 'execute', 'collect', 'stop'}):
                continue
            if declaration['id'] == 'factory.standard_benchmark' and name == 'submit':
                # This package has no cancel capability yet. It cannot own live
                # children under the new scheduler until its lifecycle is ported.
                continue
            takes = {key: port(value, declaration['defs']) for key, value in spec['takes'].items()}
            gives = {key: port(value, declaration['defs']) for key, value in spec['gives'].items()}
            lifecycle = {}
            # These are existing factory-owned durable job protocols, not CC core
            # semantics. No model/provider supplied operation can opt itself in.
            if declaration['id'] in {'factory.builder', 'factory.lab_client'} and name in {'submit', 'ab_submit'}:
                prefix = 'ab_' if name == 'ab_submit' else ''
                lifecycle = dict(status=prefix + 'status', result=prefix + 'result', cancel='cancel')
            if declaration['id'] in {'factory.inference_lab', 'factory.integration_skill', 'factory.expert_streaming'}:
                aliases = {'build_submit': ('build_status', 'build_result', 'build_cancel'),
                           'lab_submit': ('lab_status', 'lab_result', 'lab_cancel'),
                           'lab_ab_submit': ('lab_ab_status', 'lab_ab_result', 'lab_cancel')}
                if name in aliases:
                    lifecycle = dict(zip(('status', 'result', 'cancel'), aliases[name]))
            if lifecycle and any(operation not in declaration['capabilities'] for operation in lifecycle.values()):
                raise ValueError('Incomplete factory lifecycle for ' + declaration['id'] + ':' + name)
            result.append(Capability(declaration['id'] + ':' + name, spec['does'], release, name,
                {key: value['kind'] for key, value in takes.items()},
                {key: value['kind'] for key, value in gives.items()},
                frozenset(key for key, value in takes.items() if value['optional'] or (lifecycle and key == 'idem_key')),
                tuple(spec['changes']), lifecycle))
    if len({cap.id for cap in result}) != len(result):
        raise ValueError('Select exactly one release for each CC package')
    return result
