"""Protected native-channel startup policy with stale enabled legacy settings."""
import pytest
from scripts.research_foundation import exercise

from jiuwenswarm.research.native_profile import native_channel_config


def test_m1_channel_allowlist_or_owned_tmux():
    exercise('M1-001/V17')


def test_observed_readiness_and_security_prerequisites():
    exercise('M1-006/V05')


def test_native_endpoint_topology():
    exercise('M1-006/V06')


def test_stale_external_channels_cannot_reach_constructor_configuration():
    external = ("feishu", "feishu_enterprise", "xiaoyi", "dingtalk", "telegram", "discord",
                "slack", "whatsapp", "wecom", "wechat", "ssh", "a2a", "acp")
    stale = {name: {"enabled": True, "token": "public-test-canary"} for name in external}
    stale["web"] = {"enabled": True}
    filtered = native_channel_config(stale, protected=True)
    assert filtered == {"web": {"enabled": True}}
    assert all(stale[name]["enabled"] for name in external)
    filtered["web"]["enabled"] = False
    assert stale["web"]["enabled"] is True


def test_ordinary_native_profile_preserves_existing_configuration():
    configuration = {"telegram": {"enabled": True}}
    assert native_channel_config(configuration, protected=False) is configuration


@pytest.mark.filterwarnings('ignore:invalid escape sequence:SyntaxWarning')
def test_pinned_native_provider_and_durable_capture_initialize_without_model_access(tmp_path):
    from openjiuwen.core.common.logging.log_config import configure_log_config
    configure_log_config({'backend': 'default', 'log_path': str(tmp_path / 'logs'), 'output': ['console']})
    from jiuwenswarm.research.trajectory import start_native_capture, stop_native_capture, capture_healthy
    journal = start_native_capture(tmp_path / 'trajectory')
    try:
        assert capture_healthy()
        assert journal.path.is_file()
        assert start_native_capture(tmp_path / 'trajectory') is journal
    finally:
        stop_native_capture()
    assert not capture_healthy()
