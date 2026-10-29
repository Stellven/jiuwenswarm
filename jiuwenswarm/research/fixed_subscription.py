"""Finite model deployments through native Codex; names never come from prompts."""
from .contracts import ResearchError


DEFAULT_REQUESTED_MODEL = 'gpt-6.1-sol'
SPARK_REQUESTED_MODEL = 'Qwen3.8-27B-NVFP4'
# QName identifies the installed Spark backend. Its factory separately verifies
# the protected host profile and attestation; this metadata never grants a URL.
REQUESTED_MODELS = frozenset((DEFAULT_REQUESTED_MODEL, 'gpt-6-luna', 'gpt-5.6-terra', SPARK_REQUESTED_MODEL))
FIXED_DEPLOYMENT_SCHEMAS = frozenset(('ai4r-fixed-subscription:1', 'ai4r-fixed-subscription:2'))
HOST_CODEX_BACKEND = 'host-codex-app-server'


def require_requested_model(value):
    if not isinstance(value, str) or value not in REQUESTED_MODELS:
        raise ResearchError('deployment_binding', 'Unsupported explicit fixed subscription model')
    return value


def deployment_model(value):
    fields = {'schema', 'id', 'route_id', 'requested_model', 'endpoint'}
    if isinstance(value, dict) and value.get('schema') == 'ai4r-fixed-subscription:2':
        fields |= {'backend', 'reasoning_effort'}
        if (value.get('backend') != HOST_CODEX_BACKEND or value.get('reasoning_effort') != 'medium'
                or value.get('requested_model') != DEFAULT_REQUESTED_MODEL):
            raise ResearchError('deployment_binding', 'Unsupported fixed host subscription deployment')
    if (not isinstance(value, dict) or set(value) != fields
            or value['schema'] not in FIXED_DEPLOYMENT_SCHEMAS or not isinstance(value['id'], str) or not value['id']
            or value['route_id'] != 'codex-cli-default' or value['endpoint'] != 'local-protected-IPC'):
        raise ResearchError('deployment_binding', 'Unsupported fixed subscription deployment')
    return require_requested_model(value['requested_model'])


def deployment_backend(value):
    requested = deployment_model(value)
    return value['backend'] if value['schema'] == 'ai4r-fixed-subscription:2' else (
        'spark' if requested == SPARK_REQUESTED_MODEL else 'codex')


def require_profile_model(profile, requested_model, *, backend=None):
    if (not isinstance(profile, dict) or profile.get('schema') not in {'ai4r-local-profile:1', 'ai4r-local-profile:2'}
            or profile.get('model') != require_requested_model(requested_model)):
        raise ResearchError('deployment_binding', 'Fixed subscription profile and deployment models differ')
    if profile['schema'] == 'ai4r-local-profile:2' and (
            set(profile) != {'schema', 'id', 'model', 'hardware_ceiling', 'backend', 'reasoning_effort'}
            or profile.get('backend') != HOST_CODEX_BACKEND or profile.get('reasoning_effort') != 'medium'
            or profile['model'] != DEFAULT_REQUESTED_MODEL):
        raise ResearchError('deployment_binding', 'Unsupported fixed host subscription profile')
    if profile['schema'] == 'ai4r-local-profile:1' and set(profile) & {'backend', 'reasoning_effort'}:
        raise ResearchError('deployment_binding', 'Legacy subscription profile cannot select a host backend')
    actual_backend = profile.get('backend', 'spark' if requested_model == SPARK_REQUESTED_MODEL else 'codex')
    if backend is not None and actual_backend != backend:
        raise ResearchError('deployment_binding', 'Fixed subscription profile and deployment backends differ')
