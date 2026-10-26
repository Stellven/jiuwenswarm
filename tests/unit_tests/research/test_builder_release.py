"""Builder protocol dispatch keeps historical releases and future body revisions."""
import pytest
from jiuwenswarm.research.builder_release import (
    builder_mode,builder_operation,builder_receipt_contract,builder_supports_actions,
    builder_supports_provisioning,builder_uses_launcher,
)


def declaration(version,carrier='builder_agent.py',name='research.builder'):
    return {'identity':{'name':name,'version_label':version,'carrier':{'ref':carrier}}}


def test_historical_release_operations_and_receipts_keep_their_meaning():
    for serial in range(1,19):
        version='m1-'+str(serial);d=declaration(version,'builder_loop.py' if serial==13 else 'builder_agent.py')
        mode='launcher' if serial==1 else 'text' if serial<13 else 'loop' if serial==13 else 'agent'
        assert builder_mode(d)==mode
        assert builder_uses_launcher(version)==(serial==1)
        assert builder_supports_actions(d)==(serial>=17)
        assert builder_supports_provisioning(d)==(serial>=13)
        assert builder_operation(d)==('builder_action' if serial>=14 else 'builder_test' if serial==13 else 'collect_builder')
        assert builder_receipt_contract(d)==('urn:ai4r:prediction-build-receipt:4.0.0' if serial>=14 else 'urn:ai4r:prediction-build-receipt:3.0.0' if serial==13 else 'urn:ai4r:prediction-build-receipt:2.0.0' if serial>=11 else 'build-receipt')


def test_new_native_agent_implementation_revisions_share_protocol():
    for version in ('m1-19','m1-20-cache','m1-21-cache','m1-22-cache','m1-23'):
        d=declaration(version)
        assert builder_mode(d)=='agent'
        assert builder_supports_actions(d) and builder_supports_provisioning(d)
        assert builder_operation(d)=='builder_action'
        assert builder_receipt_contract(d)=='urn:ai4r:prediction-build-receipt:4.0.0'
        assert not builder_uses_launcher(version)


def test_label_cannot_grant_native_operations_to_another_carrier_or_capsule():
    for d in (declaration('m1-21-cache','builder_text.py'),declaration('m1-21-cache',name='research.benchmark'),declaration('m2-21-cache')):
        assert builder_mode(d) is None
        assert not builder_supports_actions(d) and not builder_supports_provisioning(d)
    assert builder_uses_launcher('unknown')
