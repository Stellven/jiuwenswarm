"""Evidence-aware verifier binding marks review_evidence optional (live run pl10).

Evaluation's work passed all checks, then binding its m1-5-evidence-1
verifier raised input_authority: the host built review_evidence as a
required port while the verifier declares it optional.
"""
from types import SimpleNamespace

from jiuwenswarm.research.compiler import VerifierBindings

REF = {'id': 'blob:' + 'a' * 64, 'sha256': 'a' * 64}


class _Factory:
    def __init__(self):
        self.inputs = None
        self.store = SimpleNamespace(read_record=lambda ref: {'bindings': [{'declaration_ref': REF}]})

    def bind_subnode(self, parent_ref, subnode_id, inputs, role):
        self.inputs = inputs
        return 'verifier-ref', None, None


def _ports(review_evidence_ref):
    factory = _Factory()
    VerifierBindings(factory, 'parent', 'work', {'out': 'work.verifier'}).bind('out', REF, review_evidence_ref=review_evidence_ref)
    return {port['name']: port for port in factory.inputs}


def test_review_evidence_is_bound_as_the_declared_optional_port():
    ports = _ports(REF)
    assert ports['review_evidence']['required'] is False and ports['review_evidence']['artifact_refs'] == [REF]
    assert ports['subject_declaration']['required'] is True and ports['subject_output']['required'] is True


def test_output_only_review_has_no_evidence_port():
    assert set(_ports(None)) == {'subject_declaration', 'subject_output'}

