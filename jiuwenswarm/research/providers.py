"""Once-only approved API dispatch through the pinned native model client.

The protected resolver rechecks deployment qualification, scope and revocation.
Only the bridge owns this object and the credential environment. The router
receives neither. Native parser observations precede lossy usage normalization.
"""
from __future__ import annotations

import asyncio
import copy
import inspect
import math
import re
from collections.abc import Mapping
from urllib.parse import urlsplit
from types import MappingProxyType

from .bridge import observed_usage


class ProviderError(RuntimeError):
    def __init__(self, code, *, outcome_unknown=False, observation=None):
        super().__init__(code)
        self.code = code
        self.outcome_unknown = outcome_unknown
        self.observation = copy.deepcopy(observation) if observation is not None else None


def _get(value, name, default=None):
    return value.get(name, default) if isinstance(value, Mapping) else getattr(value, name, default)


async def _await(value):
    return await value if inspect.isawaitable(value) else value


def native_client(config, model):
    # No Model wrapper: it emits the full model-client configuration in callback
    # extras. This lower native client is the audited, once-only adapter seam.
    from openjiuwen.core.foundation.llm.model_clients import create_model_client
    from openjiuwen.core.foundation.llm.schema.config import ModelClientConfig, ModelRequestConfig
    return create_model_client(ModelClientConfig(**config), ModelRequestConfig(**model))


def error_code(error):
    seen = set()
    current = error
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        status = getattr(current, "status_code", None)
        if status in {401, 403}: return "auth_failed"
        if status == 429: return "rate_limited"
        if isinstance(status, int) and 400 <= status < 500: return "invalid_request"
        if isinstance(status, int) and status >= 500: return "provider_error"
        if isinstance(current, TimeoutError) or type(current).__name__ in {"APITimeoutError", "ReadTimeout", "ConnectTimeout"}:
            return "timeout"
        if isinstance(current, (ConnectionError, OSError)) or type(current).__name__ == "APIConnectionError":
            return "network_error"
        current = current.__cause__ or current.__context__
    return "provider_error"


def observed_request_id(error):
    """Read the SDK's typed request identifier, never its raw message/body."""
    seen = set()
    while error is not None and id(error) not in seen:
        seen.add(id(error))
        value = getattr(error, 'request_id', None)
        if isinstance(value, str) and value: return value
        error = error.__cause__ or error.__context__
    return None


class NativeProviders:
    def __init__(self, *, resolve_deployment, resolve_endpoint, credential_environment,
                 native_factory=native_client):
        self.resolve_deployment, self.resolve_endpoint = resolve_deployment, resolve_endpoint
        self.environment = MappingProxyType(dict(credential_environment))
        self.factory = native_factory

    async def _configuration(self, deployment_ref, *, timeout_s, call_function):
        if (call_function not in {"worker", "planner", "verifier", "routing_selection"} or type(timeout_s) not in (int, float)
                or not math.isfinite(timeout_s) or not 0 < timeout_s <= 600):
            raise ProviderError("invalid_request")
        # The protected resolver must verify the exact Ref, approved deployment
        # evidence and current revocation before returning this detached record.
        deployment = await _await(self.resolve_deployment(deployment_ref, call_function))
        if not isinstance(deployment, Mapping):
            raise ProviderError("invalid_request")
        endpoint = await _await(self.resolve_endpoint(deployment.get("endpoint_ref")))
        if not isinstance(endpoint, Mapping):
            raise ProviderError("invalid_request")
        required = {"provider_id", "base_url", "models", "credential_env_var", "timeout_s", "enabled"}
        if set(endpoint) != required or type(endpoint["enabled"]) is not bool:
            raise ProviderError("invalid_request")
        if not endpoint["enabled"]:
            raise ProviderError("auth_failed")
        if (not re.fullmatch(r"[a-z][a-z0-9_.-]{0,63}", str(endpoint["provider_id"]))
                or deployment.get("provider") != endpoint["provider_id"]):
            raise ProviderError("invalid_request")
        url = urlsplit(endpoint["base_url"])
        local = deployment.get('adapter_id') == 'native-local-openai-chat-v1'
        if not local and call_function not in {'worker', 'planner'}:
            raise ProviderError('invalid_request')
        if local:
            from .local_pool_registry import local_endpoint_url
            if endpoint['provider_id'] != 'local' or not local_endpoint_url(endpoint['base_url']):
                raise ProviderError('invalid_request')
        elif url.scheme != "https" or not url.hostname or url.username or url.password or url.query or url.fragment:
            raise ProviderError("invalid_request")
        models = endpoint["models"]
        requested = {"model_id": deployment.get("model_id"), "provider_model_name": deployment.get("provider_model_name")}
        if (not isinstance(models, list) or not models or any(not isinstance(m, dict) or set(m) != set(requested) for m in models)
                or models.count(requested) != 1 or any(not isinstance(v, str) or not v for v in requested.values())):
            raise ProviderError("invalid_request")
        name = endpoint["credential_env_var"]
        if not isinstance(name, str) or not re.fullmatch(r"[A-Z][A-Z0-9_]{0,63}", name):
            raise ProviderError("invalid_request")
        key = self.environment.get(name)
        if not local and (not isinstance(key, str) or not key.strip()):
            raise ProviderError("auth_failed")
        provider_timeout = endpoint["timeout_s"]
        if type(provider_timeout) not in (int, float) or not math.isfinite(provider_timeout) or not 1 <= provider_timeout <= 600:
            raise ProviderError("invalid_request")
        # This parser/transport is qualified independently of all other native
        # providers. Unknown adapters remain unavailable, even if registered.
        if deployment.get("adapter_id") not in {"native-openai-chat-v1", 'native-local-openai-chat-v1'} or not deployment.get("revision"):
            raise ProviderError("invalid_request")
        timeout = min(timeout_s, provider_timeout)
        config = {"client_id": "governed-api-call", "client_provider": "OpenAI", "api_mode": "chat_completions",
                  "api_key": key, "api_base": endpoint["base_url"], "timeout": timeout,
                  "max_retries": 0, "use_shared_llm_http_client": False}
        model = {"model_name": deployment["provider_model_name"]}
        if local:
            config.update(auth_mode='none', api_key='')
            output_tokens = deployment.get('output_tokens')
            if type(output_tokens) is not int or not 256 <= output_tokens <= 32768:
                raise ProviderError('invalid_request')
            thinking = deployment.get('reasoning_enabled', False)
            role_policy = deployment.get('reasoning_role_policy')
            if role_policy is not None:
                if role_policy != 'worker_medium_assessor_verifier_none:1':
                    raise ProviderError('invalid_request')
                thinking = call_function in {'worker','planner'}
            if type(thinking) is not bool or deployment.get('reasoning_effort', 'medium') not in {'low','medium','high'}:
                raise ProviderError('invalid_request')
            extra = {'chat_template_kwargs': {'enable_thinking': thinking}}
            if thinking:
                extra['reasoning_effort'] = deployment.get('reasoning_effort', 'medium')
            elif role_policy:
                extra['reasoning_effort'] = 'none'
            model.update(max_tokens=output_tokens, temperature=1.0, top_p=0.95, extra_body=extra)
        return deployment, config, model

    async def preflight(self, deployment_ref, *, timeout_s, call_function):
        """Resolve private prerequisites without constructing/sending a client.

        The bridge runs this before final protected/frozen-decision rechecks.
        No credential-bearing configuration is returned or captured. Dispatch
        resolves the configuration again, retaining the actual effect boundary.
        """
        await self._configuration(deployment_ref, timeout_s=timeout_s, call_function=call_function)

    async def invoke(self, deployment_ref, prompt, *, timeout_s, call_function, output_tokens=None):
        if not isinstance(prompt, str) or not prompt.strip():
            raise ProviderError("invalid_request")
        deployment, config, model = await self._configuration(deployment_ref, timeout_s=timeout_s,
                                                              call_function=call_function)
        timeout = config["timeout"]
        if output_tokens is not None:
            if (deployment.get('adapter_id') != 'native-local-openai-chat-v1' or type(output_tokens) is not int
                    or not 1 <= output_tokens <= model['max_tokens']):
                raise ProviderError('invalid_request')
            model['max_tokens'] = output_tokens
        observation = {"identity": {"effective": None, "basis": "effective model not observed"},
                       "usage": observed_usage(), "provider_request_id": None}
        started = False
        truncated = False
        try:
            client = self.factory(config, model)
            parser = getattr(client, "_parse_response", None)
            if parser is None:
                raise ProviderError("invalid_request")
            async def observe(response, *args, **kwargs):
                nonlocal truncated
                choices = _get(response, 'choices', [])
                truncated = bool(choices and _get(choices[0], 'finish_reason') == 'length')
                usage = _get(response, "usage")
                observation["usage"] = observed_usage({
                    "input_tokens": _get(usage, "prompt_tokens"),
                    "output_tokens": _get(usage, "completion_tokens")})
                effective = _get(response, "model")
                if isinstance(effective, str) and effective:
                    observation["identity"] = {"effective": effective, "basis": "provider response.model"}
                request_id = _get(response, "_request_id")
                if isinstance(request_id, str) and request_id:
                    observation["provider_request_id"] = request_id
                return await parser(response, *args, **kwargs)
            client._parse_response = observe
            async with asyncio.timeout(timeout):
                started = True
                response = await client.invoke(messages=[{"role": "user", "content": prompt}], tools=None,
                                               model=deployment["provider_model_name"], timeout=timeout)
            text = _get(response, "content")
            if truncated or not isinstance(text, str) or not text.strip() or _get(response, "tool_calls"):
                raise ProviderError("invalid_output")
            return {"text": text, **observation, "observed_runtime": True}
        except asyncio.CancelledError as error:
            error.observation = copy.deepcopy({**observation, 'observed_runtime': started})
            raise
        except ProviderError as error:
            error.observation = copy.deepcopy({**observation, 'observed_runtime': started})
            raise
        except Exception as error:
            code = error_code(error)
            if observation['provider_request_id'] is None:
                observation['provider_request_id'] = observed_request_id(error)
            raise ProviderError(code, outcome_unknown=code in {"network_error", "timeout"},
                observation={**observation, 'observed_runtime': started}) from None
