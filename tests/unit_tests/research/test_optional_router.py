"""The optional selector receives only fixed authority and cannot block core."""
import copy
import subprocess

import pytest

from jiuwenswarm.research.optional_router import (
    OptionalRouter, RouterStartupError, router_environment, validate_router_config)


def config():
    ref = {'id': 'example', 'sha256': 'a' * 64}
    return {'socket_path': '/run/ai4r-router/router.sock', 'audit_root': '/var/lib/ai4r-router',
            'allowed_peer_uids': [10001], 'data_roots': ['/run/ai4r-routing/public'],
            'ref_index_path': '/run/ai4r-routing/public/ref-index.json',
            'catalog_ref': ref, 'profile_refs': [ref], 'development_profiles_ref': ref,
            'adapter_revision': 'test-pinned-revision'}


def test_router_configuration_has_no_main_store_or_unbounded_peer_authority():
    assert validate_router_config(config()) == config()
    for field, value in [('data_roots', ['/var/lib/ai4r']), ('allowed_peer_uids', [0, 10001]),
                         ('socket_path', '/run/ai4r/model.sock'), ('audit_root', '/var/lib/ai4r')]:
        changed = copy.deepcopy(config()); changed[field] = value
        with pytest.raises(RouterStartupError): validate_router_config(changed)
    for field in ('credential', 'command', 'endpoint_url', 'ref_index'):
        changed = copy.deepcopy(config()); changed[field] = 'unauthorized'
        with pytest.raises(RouterStartupError): validate_router_config(changed)


def test_router_environment_is_an_allowlist_before_process_creation():
    result = router_environment({'PATH': '/trusted/bin', 'LANG': 'C.UTF-8', 'OPENAI_API_KEY': 'sentinel',
        'HOME': '/main-account', 'JIUWENSWARM_M1_CONFIG': '/main-config', 'PYTHONPATH': '/untrusted'})
    assert result == {'PATH': '/trusted/bin', 'LANG': 'C.UTF-8', 'PYTHONUNBUFFERED': '1',
                      'PYTHONDONTWRITEBYTECODE': '1'}


def test_absent_optional_router_never_starts_a_child():
    assert OptionalRouter.start({}) is None


def test_cleanup_waits_for_its_exact_child_and_reaps_after_kill():
    class Child:
        def __init__(self): self.events = []
        def poll(self): return None
        def terminate(self): self.events.append('terminate')
        def kill(self): self.events.append('kill')
        def wait(self, timeout):
            self.events.append(('wait', timeout))
            if timeout == 5: raise subprocess.TimeoutExpired('owned-router', timeout)
    child = Child()
    OptionalRouter(child, None).close()
    assert child.events == ['terminate', ('wait', 5), 'kill', ('wait', 2)]
