"""Builder release protocol families, independent of admission authority.

The m1 release lineage keeps historical behavior. Serial 19 onward versions the
native-agent implementation while retaining its operation/receipt protocol; a
new protocol requires a new family here, not an ever-growing release whitelist.
Every caller must still validate the exact captured declaration and admission.
"""
from __future__ import annotations
import re


def _serial(version):
    if not isinstance(version, str):
        return None
    match = re.fullmatch(r'm1-([1-9][0-9]*)(-cache)?', version)
    if match is None:
        return None
    serial = int(match[1])
    if match[2] and serial < 19:
        return None
    return serial


def builder_mode(declaration):
    identity = declaration.get('identity', {})
    if identity.get('name') != 'research.builder':
        return None
    serial = _serial(identity.get('version_label'))
    if serial is None:
        return None
    carrier = identity.get('carrier', {}).get('ref')
    # New implementation revisions must bind the actual native agent carrier.
    # A version-shaped label alone cannot select scientific execution operations.
    if serial >= 19 and carrier != 'builder_agent.py':
        return None
    if serial >= 14:
        return 'agent'
    if serial == 13 and carrier == 'builder_loop.py':
        return 'loop'
    return 'text' if serial >= 2 else 'launcher'


def builder_uses_launcher(version):
    serial = _serial(version)
    return serial is None or serial == 1


def builder_supports_actions(declaration):
    return builder_mode(declaration) == 'agent' and _serial(declaration['identity']['version_label']) >= 17


def builder_supports_provisioning(declaration):
    return builder_mode(declaration) in {'agent', 'loop'} or (
        declaration.get('identity', {}).get('name') == 'research.builder'
        and declaration['identity'].get('version_label') == 'm1-13')


def builder_operation(declaration):
    mode = builder_mode(declaration)
    return 'builder_action' if mode == 'agent' else 'builder_test' if mode == 'loop' else 'collect_builder'


def builder_receipt_contract(declaration):
    mode = builder_mode(declaration)
    if mode == 'agent':
        return 'urn:ai4r:prediction-build-receipt:4.0.0'
    if mode == 'loop':
        return 'urn:ai4r:prediction-build-receipt:3.0.0'
    return ('urn:ai4r:prediction-build-receipt:2.0.0'
            if declaration.get('identity', {}).get('version_label') in {'m1-11', 'm1-12', 'm1-13'}
            else 'build-receipt')
