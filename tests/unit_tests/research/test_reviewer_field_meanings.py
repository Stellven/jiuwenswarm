"""Reviewers see the output contract's field meanings (stopgap C).

Live run pl1 (2026-10-29): the Hypothesis reviewer returned INCONCLUSIVE on
max_patch_files because the contract meaning never reached it.
"""
from jiuwenswarm.research.checks.schema_context import frozen_output_instructions
from jiuwenswarm.research.contracts import field_meanings


def _declaration(*refs):
    return {'ports': {'outputs': [{'name': 'out%d' % n, 'schema_ref': ref, 'required': True} for n, ref in enumerate(refs)]}}


def test_meanings_cover_the_interface_and_referenced_types():
    meanings = dict(field_meanings('hypothesis-blueprint:field-contract:2'))
    assert 'implementation files only' in meanings['ImplementationScope.max_patch_files']
    assert field_meanings('urn:jiuwenswarm:m1-design:intent-ir:1.0.0') == ()


def test_instructions_carry_meanings_only_when_opted_in():
    declaration = _declaration('hypothesis-blueprint:field-contract:2')
    plain = frozen_output_instructions(b'base', declaration)
    with_meanings = frozen_output_instructions(b'base', declaration, meanings=True)
    assert b'Fixed field meanings' not in plain and with_meanings.startswith(plain)
    assert 'implementation files only'.encode() in with_meanings


def test_urn_outputs_are_byte_identical_with_or_without_meanings():
    declaration = _declaration('urn:jiuwenswarm:m1-design:intent-ir:1.0.0')
    assert frozen_output_instructions(b'base', declaration) == frozen_output_instructions(b'base', declaration, meanings=True)
