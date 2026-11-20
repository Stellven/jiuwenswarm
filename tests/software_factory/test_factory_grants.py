"""Delegated Research grants remain scoped away from native Factory operations."""
import hashlib
import json
import time

import pytest

from jiuwenswarm.research.contracts.types import Principal, ResearchError
from jiuwenswarm.research.shell_auth import SessionAuthority


@pytest.mark.parametrize('kind', ('evaluation_http', 'runner_http'))
def test_factory_requires_native_grant_even_with_matching_operations(tmp_path, kind):
    authority = SessionAuthority(tmp_path / 'sessions', 'http://127.0.0.1:5175')
    principal = Principal('alice', frozenset({'workspace'}), frozenset({'submit', 'status'}))
    try:
        authority.initialize(principal)
        native = authority.token_path.read_text()
        native_digest = hashlib.sha256(native.encode()).hexdigest()
        context = {
            'account_id': 'alice', 'workspace_id': 'workspace', 'profile_id': 'profile',
            'configuration_ref': {'id': 'configuration', 'sha256': 'a' * 64},
            'profile_ref': {'id': 'profile', 'sha256': 'b' * 64},
        }
        authority.configure_evaluation(context, run_lookup=lambda _: None, run_reconcile=lambda *_: [])
        _, startup_sha256 = authority._startup_evaluation()

        # Populate one disposable grant record to exercise actual permission
        # checks without requiring root-owned credential issuance in unit tests.
        delegated = 'isolated-delegated-bearer-token'
        digest = hashlib.sha256(delegated.encode()).hexdigest()
        authority.db.execute('INSERT INTO grants(digest,family,kind,principal) VALUES(?,?,?,?)',
                             (digest, 'isolated', kind, authority._encode(principal)))
        if kind == 'evaluation_http':
            authority.db.execute('INSERT INTO evaluation_grants VALUES(?,?,?,?)',
                                 ('evaluation:test', digest, json.dumps(context), startup_sha256))
        else:
            authority.db.execute('INSERT INTO runner_grants VALUES(?,?,?,?)',
                                 ('runner:test', digest, native_digest, time.time() + 60))

        for operation in ('submit', 'status'):
            assert authority.authenticate('Bearer ' + delegated, operation) == principal
            assert authority.authenticate_native_http('Bearer ' + native, operation) == principal
            with pytest.raises(ResearchError) as denied:
                authority.authenticate_native_http('Bearer ' + delegated, operation)
            assert denied.value.details == {'http_status': 403}
    finally:
        authority.close()
