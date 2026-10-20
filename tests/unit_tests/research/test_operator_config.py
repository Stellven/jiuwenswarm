"""Closed operator configuration: source field-catalog operator-config 1.0.0."""
import copy
import json

import pytest


def test_api_credentials_use_process_start_environment_before_legacy_dotenv(tmp_path):
    import os
    import subprocess
    import sys
    path = tmp_path / 'legacy.env'
    path.write_text('APPROVED_TEST_API_KEY=legacy-sentinel\n', encoding='utf-8')
    script = """import sys
from jiuwenswarm.research.native_profile import startup_credential_environment
from jiuwenswarm.dotenv_early import load_dotenv_runtime
load_dotenv_runtime(sys.argv[1], override=True)
assert startup_credential_environment()['APPROVED_TEST_API_KEY'] == 'startup-sentinel'
try:
    startup_credential_environment()['APPROVED_TEST_API_KEY'] = 'changed'
    raise AssertionError('mutable protected environment')
except TypeError:
    pass
"""
    result = subprocess.run([sys.executable, '-c', script, str(path)], capture_output=True,
        env={**os.environ, 'JIUWENSWARM_M1_PROFILE':'1', 'APPROVED_TEST_API_KEY':'startup-sentinel'}, timeout=10)
    assert result.returncode == 0, result.stderr.decode()

from jiuwenswarm.research.operator_config import ConfigError, OperatorConfiguration


def valid_config():
    ref = {"id": "policy", "sha256": "a" * 64}
    return {
        "schema_version": "1.0.0",
        "cc": {"plan_source": "static", "plan_policy_ref": ref,
               "static_template_ref": {**ref, "id": "template"},
               "evaluation_profile_ref": None,
               "router": {"enabled": False, "deadline_s": 30, "profile_ref": None}},
        "rsi": {"custodian_key_id": None, "custodian_public_key": None},
        "codex": {"route_id": "codex-cli-default"},
        "role_aliases": {k: "codex-cli-default" for k in ("searcher", "builder", "verifier")},
    }


def test_legacy_dotenv_cannot_override_protected_startup_authority(tmp_path, monkeypatch):
    from jiuwenswarm.research import native_profile
    from jiuwenswarm.dotenv_early import load_dotenv_runtime
    snapshot = {key: value for key, value in __import__('os').environ.items() if native_profile.protected_key(key)}
    snapshot.update(JIUWENSWARM_M1_PROFILE='1', JIUWENSWARM_M1_ORIGIN='http://127.0.0.1:5173',
                    JIUWENSWARM_M1_ACCOUNTS='/protected/accounts', JIUWENSWARM_AGENT_SDK='codex_subscription')
    monkeypatch.setattr(native_profile, 'M1_PROFILE', True)
    monkeypatch.setattr(native_profile, '_PROTECTED_STARTUP', snapshot)
    for key, value in snapshot.items(): monkeypatch.setenv(key, value)
    monkeypatch.setenv('JIUWENSWARM_M1_ADDED_BY_DOTENV', 'must disappear')
    dotenv = tmp_path / 'legacy.env'
    dotenv.write_text('JIUWENSWARM_M1_PROFILE=0\nJIUWENSWARM_M1_ORIGIN=http://untrusted.invalid\nJIUWENSWARM_M1_ACCOUNTS=/untrusted\nJIUWENSWARM_AGENT_SDK=other\n', encoding='utf-8')
    load_dotenv_runtime(dotenv)
    import os
    for key, value in snapshot.items(): assert os.environ[key] == value
    assert 'JIUWENSWARM_M1_ADDED_BY_DOTENV' not in os.environ


def test_exact_configuration_snapshot_is_detached():
    original = valid_config()
    config = OperatorConfiguration.from_mapping(original)
    original["cc"]["router"]["enabled"] = True
    assert config.snapshot() == valid_config()
    returned = config.snapshot()
    returned["role_aliases"]["verifier"] = "foreign"
    assert config.snapshot() == valid_config()


@pytest.mark.parametrize("section", [None, "cc", "rsi", "codex", "role_aliases", "router"])
def test_unknown_keys_are_refused_without_echoing_values(section):
    data = valid_config()
    target = data if section is None else data["cc"]["router"] if section == "router" else data[section]
    target["api_key"] = "private-canary"
    with pytest.raises(ConfigError) as error:
        OperatorConfiguration.from_mapping(data)
    assert "private-canary" not in str(error.value)


@pytest.mark.parametrize("key", ["schema_version", "cc", "rsi", "codex", "role_aliases"])
def test_missing_required_top_level_key(key):
    data = valid_config()
    del data[key]
    with pytest.raises(ConfigError):
        OperatorConfiguration.from_mapping(data)


@pytest.mark.parametrize("patch", [
    {"enabled": "false"}, {"enabled": 0}, {"deadline_s": True},
    {"deadline_s": 29}, {"deadline_s": 31}, {"deadline_s": float("nan")},
    {"profile_ref": {"id": "profile", "sha256": "A" * 64}},
])
def test_router_types_and_fixed_deadline(patch):
    data = valid_config()
    data["cc"]["router"].update(patch)
    with pytest.raises(ConfigError):
        OperatorConfiguration.from_mapping(data)


def test_non_codex_role_is_refused():
    data = valid_config()
    data["role_aliases"]["builder"] = "some-api"
    with pytest.raises(ConfigError, match="ROLE_ALIAS"):
        OperatorConfiguration.from_mapping(data)


def test_enabled_router_needs_resolved_approved_profile():
    data = valid_config()
    data["cc"]["router"]["enabled"] = True
    with pytest.raises(ConfigError, match="EVALUATION_PROFILE"):
        OperatorConfiguration.from_mapping(data)
    data["cc"]["evaluation_profile_ref"] = {"id": "evaluation", "sha256": "b" * 64}
    with pytest.raises(ConfigError, match="EVALUATION_PROFILE"):
        OperatorConfiguration.from_mapping(data)


def test_profile_switch_cannot_override_operator_file():
    data = valid_config()
    data["cc"]["evaluation_profile_ref"] = {"id": "evaluation", "sha256": "b" * 64}
    with pytest.raises(ConfigError, match="PROFILE_SWITCH"):
        OperatorConfiguration.from_mapping(data, resolve_profile=lambda ref: {"router_enabled": True})


@pytest.mark.parametrize("key,value", [("custodian_key_id", "key-1"), ("custodian_public_key", "a" * 43)])
def test_custodian_public_half_is_an_atomic_pair(key, value):
    data = valid_config()
    data["rsi"][key] = value
    with pytest.raises(ConfigError, match="CUSTODIAN"):
        OperatorConfiguration.from_mapping(data)


def test_null_custodian_key_is_valid_and_disables_candidate_admission():
    assert OperatorConfiguration.from_mapping(valid_config()).snapshot()["rsi"] == {
        "custodian_key_id": None, "custodian_public_key": None,
    }


def test_yaml_loader_refuses_duplicate_keys_and_untrusted_tags(tmp_path):
    config = tmp_path / "config.yaml"
    config.write_text("schema_version: '1.0.0'\nschema_version: '1.0.0'\n", encoding="utf-8")
    with pytest.raises(ConfigError):
        OperatorConfiguration.load(config)
    config.write_text("!!python/object/apply:os.system ['echo forbidden']", encoding="utf-8")
    with pytest.raises(ConfigError):
        OperatorConfiguration.load(config)


def test_load_captures_once_and_never_writes_operator_file(tmp_path):
    path = tmp_path / "config.yaml"
    data = json.dumps(valid_config()).encode()
    path.write_bytes(data)
    config = OperatorConfiguration.load(path)
    assert path.read_bytes() == data
    path.write_text("changed", encoding="utf-8")
    assert config.snapshot() == valid_config()


def test_missing_file_reports_a_stable_credential_free_error(tmp_path):
    with pytest.raises(ConfigError, match="CONFIG_UNAVAILABLE"):
        OperatorConfiguration.load(tmp_path / "missing")
