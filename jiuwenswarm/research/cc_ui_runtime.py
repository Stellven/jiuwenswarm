"""Load only fixed CC installation modules without initializing RSI engines."""
import importlib
from pathlib import Path
import sys
import types


def module(name):
    if name not in {'cc_rsi_installation', 'cc_rsi_operator', 'cc_rsi_library', 'cc_rsi_development', 'cc_rsi_capsule'}:
        raise ValueError('Unknown installed CC component')
    package = '_ai4r_cc_runtime'
    if package not in sys.modules:
        value = types.ModuleType(package)
        value.__path__ = [str(Path(__file__).resolve().parents[1] / 'server/rsi')]
        sys.modules[package] = value
    return importlib.import_module(package + '.' + name)


def attach_native_operator(channel, authority):
    channel.research_cc_operator = module('cc_rsi_installation').load_native_gateway(authority)


def attach_native_development(channel, authority, workspace_id):
    channel.research_cc_workspace = workspace_id
    channel.research_cc_development = module('cc_rsi_development').load_native_development(authority, workspace_id)
    channel.research_cc_capsules = module('cc_rsi_capsule').load_native_capsules(authority, workspace_id)
