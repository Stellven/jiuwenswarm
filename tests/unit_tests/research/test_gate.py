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
