import pytest

from jiuwenswarm.research.contracts import ResearchError
from jiuwenswarm.research.gate import assemble_assessment, zip_projection


def test_assessment_identity_and_verdict_are_host_owned():
    refs = [{"id": str(n), "sha256": str(n) * 64} for n in range(1, 4)]
    criteria = [{"criterion_id": "shape", "blocking": True}]
    reply = {"findings": [{"criterion_id": "shape", "outcome": "PASS", "reason": "output shape"}],
             "uncertainties": [], "limitations": [], "required_correction": None}
    record = assemble_assessment(reply, criteria, refs[0], refs[1], refs[2])
    assert record["subject_ref"] == refs[1]
    assert record["findings"][0]["evidence_refs"] == refs[:2]
    assert record["verdict"] == "PASS"
    for bad in (reply | {"findings": []}, reply | {"findings": reply["findings"] * 2},
                reply | {"subject_ref": refs[0]}, reply | {"required_correction": "repair"}):
        with pytest.raises(ResearchError):
            assemble_assessment(bad, criteria, *refs)


def test_zip_projection_is_exact_sorted_and_rejects_directory():
    import io
    import zipfile
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as archive:
        archive.writestr("b.txt", "two")
        archive.writestr("a.txt", "one")
    projection = zip_projection(out.getvalue()).decode()
    assert projection.index("path: a.txt") < projection.index("path: b.txt")
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as archive:
        archive.writestr("dir/", "")
    with pytest.raises(ResearchError):
        zip_projection(out.getvalue())


@pytest.mark.asyncio
async def test_semantic_review_discloses_only_declaration_and_exact_output():
    """A scope/payload check, not evidence of real model judgement quality."""
    import json
    from jiuwenswarm.research.gate import SemanticVerifier

    def ref(name):
        return {'id': name, 'sha256': 'a' * 64}

    declaration, output, profile, instructions, context = map(ref, (
        'declaration', 'output', 'profile', 'instructions', 'host-only-context'))
    # A producer's output can contain a source Ref, but it grants no lookup.
    declaration_bytes = b'{"purpose":"Produce an internally coherent research brief"}'
    output_bytes = b'{"objective":"Compare retrieval methods","source_ref":{"id":"private-input","sha256":"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"}}'
    criteria = [{'criterion_id': 'coherence', 'blocking': True, 'target_port': None}]
    reads = []

    class DeclarationOutputStore:
        def read_blob(self, identity):
            reads.append(identity['id'])
            permitted = {'declaration': declaration_bytes, 'output': output_bytes,
                         'instructions': b'Check declaration/output conformance only.'}
            assert identity['id'] in permitted, 'Semantic reviewer attempted an input/context lookup'
            return permitted[identity['id']]

        def read_record(self, identity, *, contract_id):
            assert identity == profile and contract_id == 'checking-profile'
            return {'model_call_limit': 1, 'criteria': criteria, 'instruction_ref': instructions}

        def put_record(self, contract_id, value, **_):
            assert contract_id == 'verifier-assessment'
            assert value['review_context_ref'] == context  # Local host binding, never model input.
            return ref('assessment')

    async def invoke(prompt, *, system):
        payload = json.loads(prompt)
        assert set(payload) == {'subject_declaration', 'subject_output'}
        assert payload['subject_declaration'].encode() == declaration_bytes
        assert payload['subject_output'].encode() == output_bytes
        assert 'host-only-context' not in prompt + system
        return json.dumps({'findings': [{'criterion_id': 'coherence', 'outcome': 'PASS',
                          'reason': 'Controlled assessment body for the disclosure test.'}],
                           'uncertainties': [], 'limitations': [], 'required_correction': None})

    await SemanticVerifier(DeclarationOutputStore()).review(declaration, output, profile, context, 'brief', invoke)
    assert reads == ['declaration', 'output', 'instructions']
