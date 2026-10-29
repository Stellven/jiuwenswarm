import pytest

from jiuwenswarm.research.contracts import ResearchError
from jiuwenswarm.research.runner import CapsuleArtifacts
from jiuwenswarm.research.state import SQLiteRunStore


def test_capsule_has_scoped_artifacts_and_no_acceptance_or_library_writer(tmp_path):
    store=SQLiteRunStore(tmp_path);allowed=store.put_blob(b'input');hidden=store.put_blob(b'protected')
    capture=CapsuleArtifacts(store,[allowed],scope={'run_id':'run'})
    assert capture.read_blob(allowed)==b'input'
    with pytest.raises(ResearchError,match='artifact_scope'):capture.read_blob(hidden)
    own=capture.put_blob(b'candidate');assert capture.read_blob(own)==b'candidate'
    assert not hasattr(capture,'commit_acceptance') and not hasattr(capture,'connection')
    with pytest.raises(ResearchError,match='authority_boundary'):capture.put_record('gate-decision',{})
