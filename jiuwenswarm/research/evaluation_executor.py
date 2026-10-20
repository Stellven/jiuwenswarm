"""Finite IF016 private binding over the existing scientific backend.

The live protected owner authorizes every operation first. This adapter then
independently resolves the exact private record and durable custody joins. A
binding does not grant a scientific operation, a tool allowance or readiness.
"""
from __future__ import annotations

import copy

from .bridge import BridgeError
from .contracts import ResearchError, validate
from .executor import ExecutorBlocked, RestrictedExecutor
from .state import SQLiteRunStore
from .store_custody import CustodyStore


class EvaluationExecutorAdapter:
    def __init__(self, store, backend):
        if type(store) not in (SQLiteRunStore, CustodyStore) or type(backend) is not RestrictedExecutor:
            raise ExecutorBlocked('EVALUATION_EXECUTOR_ADAPTER_UNAVAILABLE')
        self.store, self.backend = store, backend

    def is_private_reference(self, ref):
        """Classification can refuse a kind; it never supplies authority."""
        try:
            validate('Ref', ref)
            return self.store.record_kind(ref) != 'subnode-execution-contract'
        except (ResearchError, BridgeError, ValueError, TypeError, KeyError):
            raise ExecutorBlocked('EXECUTOR_CONTEXT_CUSTODY_UNAVAILABLE') from None

    def validate_binding(self, request, response):
        try:
            if type(self.store) is CustodyStore:
                child = self.store.validate_evaluation_executor_binding(request, response)
            else:
                from .evaluation_authority import validate_evaluation_executor_binding
                child = validate_evaluation_executor_binding(self.store, request, response)
            if child != response['contract']:
                raise ValueError('Private context changed')
            return copy.deepcopy(child)
        except (ResearchError, BridgeError, ValueError, TypeError, KeyError):
            raise ExecutorBlocked('EVALUATION_EXECUTOR_AUTHORIZATION_INVALID') from None

    def require_operation(self, operation, request, contract):
        # No scientific service is inferred from an admitted identity or from
        # receiving a private context. The independent declared-service/tool
        # adapter must be installed before these paths can perform effects.
        from .science_registration import InstalledScienceRuntime
        registration=getattr(self.backend,'science_registration',None)
        if type(registration) is not InstalledScienceRuntime or registration.backend is not self.backend:
            raise ExecutorBlocked('EVALUATION_EXECUTOR_OPERATION_ADAPTER_UNAVAILABLE')
        registration.require_operation(request,operation,contract)
