"""Protected process-start profile, captured before legacy dotenv loading."""
from __future__ import annotations

import copy
import os
from types import MappingProxyType

M1_PROFILE = os.environ.get("JIUWENSWARM_M1_PROFILE") == "1"
M1_REFUSAL_REASON = ('operator_configuration_unavailable'
                     if M1_PROFILE and os.environ.get('JIUWENSWARM_M1_REFUSAL_ONLY') else None)
NATIVE_CHANNELS = frozenset({"web", "cli", "tui"})


def protected_key(key):
    return (key.startswith(("JIUWENSWARM_M1_", "AI4R_")) or key in {
        "JIUWENSWARM_DATA_DIR", "JIUWENSWARM_HOME", "HOME", "JIUWENSWARM_AGENT_SDK",
        "AGENT_SERVER_HOST", "AGENT_SERVER_PORT", "AGENT_PORT", "AGENT_SERVER_URL",
        "WEB_HOST", "WEB_PORT", "WEB_PATH", "GATEWAY_HOST", "GATEWAY_PORT",
        "FRONTEND_HOST", "FRONTEND_PORT"})


_PROTECTED_STARTUP = {key: value for key, value in os.environ.items() if protected_key(key)}
_STARTUP_ENVIRONMENT = MappingProxyType(dict(os.environ))


def startup_credential_environment():
    """Approved OS startup values, before legacy dotenv; never log this map."""
    return _STARTUP_ENVIRONMENT


def restore_protected_startup():
    if not M1_PROFILE:
        return
    for key in tuple(os.environ):
        if protected_key(key) and key not in _PROTECTED_STARTUP:
            os.environ.pop(key, None)
    os.environ.update(_PROTECTED_STARTUP)


def native_channel_config(configuration, *, protected=M1_PROFILE):
    if not protected:
        return configuration
    if not isinstance(configuration, dict):
        return {}
    return {key: copy.deepcopy(value) for key, value in configuration.items() if key in NATIVE_CHANNELS}
