"""Canonical science remains usable alongside private evidence isolation."""
import json
import io
import zipfile
from pathlib import Path

import pytest

from jiuwenswarm.research.contracts import ResearchError
from jiuwenswarm.research.state import SQLiteRunStore


def test_original_canonical_evaluation_verdict_remains_product_material(tmp_path):
    payload = json.loads((Path(__file__).resolve().parents[2] / 'fixtures' / 'research'
        / 'pipeline' / 'source-valid' / 'evaluation_verdict.json').read_text(encoding='utf-8'))
    # The demonstration fixture's editorial extension is outside the adopted
    # closed contract. Capture its actual canonical scientific fields.
    payload.pop('ext')
    store = SQLiteRunStore(tmp_path)
    try:
        original = store.put_record('evaluation-verdict', payload)
        before = store.read_blob(original)
        store.require_product_material([original])
        private = store.append_record('evaluation-result', {'id': 'private:verdict-reference',
            'result': {'original_ref': original}, 'accepted': False, 'invalid_for_product': True})
        with pytest.raises(ResearchError, match='evaluation_only'):
            store.require_product_material([private])
        store.require_product_material([original])
        assert store.record_kind(original) == 'evaluation-verdict' and store.read_blob(original) == before
    finally:
        store.close()


@pytest.mark.parametrize('member', ['evaluation_export.json', 'EVALUATION_EXPORT.JSON'])
def test_claimed_private_export_name_never_becomes_product_material(tmp_path, member):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w') as archive:
        # A claimed private export is excluded even when its manifest is
        # structurally invalid; parsing {} must not grant ordinary eligibility.
        archive.writestr(member, b'{}')
    store = SQLiteRunStore(tmp_path)
    try:
        raw = stream.getvalue(); ref = store.put_blob(raw, media_type='application/zip')
        with pytest.raises(ResearchError, match='evaluation_only'):
            store.require_product_material([ref])
        assert store.read_blob(ref) == raw
    finally:
        store.close()


def test_ordinary_client_retrieval_archive_remains_product_material(tmp_path):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w') as archive:
        archive.writestr('client_retrieval.json', b'{}')
    store = SQLiteRunStore(tmp_path)
    try:
        raw = stream.getvalue(); ref = store.put_blob(raw, media_type='application/zip')
        store.require_product_material([ref])
        assert store.read_blob(ref) == raw
    finally:
        store.close()
