"""Version-independent Builder routing; all providers here are offline fakes."""
import pytest

from jiuwenswarm.research.builder_mode import builder_mode
from jiuwenswarm.research.contracts import ResearchError
from .test_bridge import Ledger, Provider, authorized_context
from jiuwenswarm.research.bridge import GovernedBridge


def declaration(version, carrier, tools=False):
    return {'identity': {'name': 'research.builder', 'version_label': version,
                         'carrier': {'ref': carrier}},
            'needs': {'model': {'tool_calling': tools}},
            'budget': {'per_call': {'tool_calls': 20 if carrier == 'builder_agent.py' else 0}}}


@pytest.mark.parametrize('version', ['m1-1'] + [f'm1-{n}' for n in range(2, 18)])
def test_historical_modes(version):
    n = int(version.split('-')[1])
    carrier, expected = (('builder.py', 'legacy') if n == 1 else
                         ('builder_text.py', 'text') if n < 13 else
                         ('builder_loop.py', 'loop') if n == 13 else
                         ('builder_agent.py', 'agent'))
    assert builder_mode(declaration(version, carrier, tools=n == 1)) == expected


@pytest.mark.parametrize('version', ['m1-18', 'future-release'])
def test_new_versions_follow_validated_carrier(version):
    assert builder_mode(declaration(version, 'builder_agent.py')) == 'agent'
    assert builder_mode(declaration(version, 'builder.py', tools=True)) == 'legacy'


@pytest.mark.parametrize('carrier,tools', [('unknown.py', False), ('builder_agent.py', True),
                                          ('builder.py', False)])
def test_unknown_or_incompatible_carriers_refused(carrier, tools):
    with pytest.raises(ResearchError, match='Unsupported admitted Builder'):
        builder_mode(declaration('future', carrier, tools))


@pytest.mark.asyncio
@pytest.mark.parametrize('version', ['m1-17', 'm1-18', 'future-release'])
async def test_bounded_builder_uses_governed_provider_without_legacy_launcher(version):
    ledger = Ledger()
    provider = Provider(ledger)
    protected = authorized_context()
    protected.update(cc_name='research.builder', cc_version=version,
                     declaration=declaration(version, 'builder_agent.py'))
    bridge = GovernedBridge(persist=ledger.append, authorize=lambda _: protected,
                            revalidate=lambda _: protected, subscription_service=provider)
    assert (await bridge.call({}, 'offline prompt'))['text'] == 'answer'
    assert provider.calls == 1


def test_current_catalog_is_bounded_action():
    from jiuwenswarm.research.capsules.assets import build_research_assets
    class Store:
        def __init__(self): self.records = {}
        def put_blob(self, raw, **kwargs):
            import hashlib
            ref = {'id': 'blob:' + hashlib.sha256(raw).hexdigest(), 'sha256': hashlib.sha256(raw).hexdigest()}
            self.records[ref['id']] = raw
            return ref
        def put_record(self, kind, value):
            import json
            from jiuwenswarm.research.state import json_bytes
            return self.put_blob(json_bytes(value))
    import json
    store = Store()
    assets = build_research_assets(store)
    declared = json.loads(store.records[assets['builder']['declaration_ref']['id']])
    assert builder_mode(declared) == 'agent'


@pytest.mark.parametrize('version', ['m1-11', 'm1-12', 'm1-13', 'future-release'])
def test_prediction_receipt_protocol_is_declaration_driven(version):
    declared = declaration(version, 'builder_text.py')
    declared['ports'] = {'outputs': [{'name': 'build_receipt',
        'schema_ref': 'urn:ai4r:prediction-build-receipt:2.0.0'}]}
    assert builder_mode(declared) == 'prediction'


@pytest.mark.asyncio
async def test_unknown_carrier_refused_before_provider_effect():
    ledger, protected = Ledger(), authorized_context()
    provider = Provider(ledger)
    protected.update(cc_name='research.builder', declaration=declaration('future', 'unknown.py'))
    bridge = GovernedBridge(persist=ledger.append, authorize=lambda _: protected,
                            revalidate=lambda _: protected, subscription_service=provider)
    with pytest.raises(ResearchError, match='Unsupported admitted Builder'):
        await bridge.call({}, 'offline prompt')
    assert provider.calls == 0
