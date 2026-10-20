"""Allowed native preferences; protected operator controls have another owner."""
from __future__ import annotations

import copy
from collections.abc import Mapping
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


class PreferenceError(ValueError):
    pass


_TEXT = {'display_name', 'timezone', 'runtime_choice', 'search_options', 'reasoning_options', 'ui_behavior'}
_PATHS = {'workspace_input', 'workspace_poc', 'knowledge_paths'}
_ALLOWED = _TEXT | _PATHS | {'single_gpu', 'ingestion_extensions'}


def resolve_preferences(account: Mapping, host: Mapping, project: Mapping, *, root: Path) -> dict:
    """Resolve allowed account -> host -> project records into a detached snapshot.

    Preference paths are local paths under the assigned workspace. They never
    authorize access to operator credentials, fixture custody or another project.
    These fields are not additions to the closed operator-config contract.
    """
    root = root.resolve()
    resolved = {}
    for record in [account, host, project]:
        if not isinstance(record, Mapping) or set(record) - _ALLOWED:
            raise PreferenceError('unknown or protected preference field')
        for key, value in record.items():
            if key in _TEXT:
                if not isinstance(value, str) or not value.strip():
                    raise PreferenceError('preference must be nonempty text')
                if key == 'timezone':
                    try:
                        ZoneInfo(value)
                    except (ZoneInfoNotFoundError, ValueError) as exc:
                        raise PreferenceError('unknown timezone') from exc
            elif key == 'single_gpu':
                if type(value) is not bool:
                    raise PreferenceError('single_gpu must be boolean')
            elif key == 'ingestion_extensions':
                if not isinstance(value, list) or not value or len(set(value)) != len(value) or not set(value) <= {'.txt', '.md', '.pdf'}:
                    raise PreferenceError('unsupported ingestion extension')
            elif key in _PATHS:
                paths = value if key == 'knowledge_paths' else [value]
                if not isinstance(paths, list) or not all(isinstance(p, str) and p for p in paths):
                    raise PreferenceError('invalid local preference path')
                for path in paths:
                    target = (root / path).resolve()
                    if not target.is_relative_to(root):
                        raise PreferenceError('preference path escapes assigned workspace')
            resolved[key] = copy.deepcopy(value)
    return resolved


def freeze_configuration(operator, account: Mapping, host: Mapping, project: Mapping, *, root: Path) -> dict:
    """Compose validated operator settings without parsing or modifying them."""
    return {'operator': operator.snapshot(), 'preferences': resolve_preferences(account, host, project, root=root)}
