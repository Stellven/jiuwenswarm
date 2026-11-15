"""Lexical historical paths independent of the machine opening a recording.

These helpers never resolve or open a path. Exact strings remain the keys in
the content-addressed bundle; pure paths are used only for ownership checks and
for joins originally performed on the recording's operating system.
"""
from __future__ import annotations

from pathlib import PurePath, PurePosixPath, PureWindowsPath
import re


def _text(value: str) -> None:
    if not isinstance(value, str) or not value or '\x00' in value:
        raise ValueError('Invalid historical path')


def _windows(value: str) -> bool:
    return bool(re.match(r'^[a-zA-Z]:', value)) or value.startswith(('\\', '//'))


def _safe(path: PurePath, original: str) -> None:
    if '..' in path.parts:
        raise ValueError('Historical path contains traversal')
    if isinstance(path, PureWindowsPath):
        normalized = original.replace('/', '\\')
        if normalized.startswith(('\\\\?\\', '\\\\.\\')):
            raise ValueError('Historical device paths are unsupported')
        if any(':' in part for part in path.parts if part != path.anchor):
            raise ValueError('Historical path contains a drive or stream component')


def historical_root(value: str) -> PurePosixPath | PureWindowsPath:
    """Recognize an absolute POSIX, drive-qualified Windows, or UNC root."""
    _text(value)
    path = PureWindowsPath(value) if _windows(value) else PurePosixPath(value)
    if not path.is_absolute() or (isinstance(path, PurePosixPath) and '\\' in value):
        raise ValueError('Historical run root must be absolute')
    _safe(path, value)
    return path


def validate_historical_member(root: str | PurePath, value: str) -> PurePath:
    """Check ownership without resolving historical paths on this machine."""
    _text(value)
    parent = historical_root(str(root))
    if isinstance(parent, PurePosixPath):
        if '\\' in value or _windows(value):
            raise ValueError('Historical path uses a foreign path flavor')
        path = PurePosixPath(value)
    else:
        path = PureWindowsPath(value)
        if (path.drive or path.root) and not path.is_absolute():
            raise ValueError('Historical path has an incomplete Windows anchor')
    _safe(path, value)
    if path.is_absolute() and not path.is_relative_to(parent):
        raise ValueError('Historical path escapes original run directory')
    return path


def historical_child(parent: str, name: str) -> str:
    """Repeat a recorded directory join using its historical path flavor."""
    _text(parent)
    if not isinstance(name, str) or not name or any(value in name for value in ('/', '\\', ':', '\x00')) or name in {'.', '..'}:
        raise ValueError('Invalid historical child name')
    flavor = PureWindowsPath if _windows(parent) or '\\' in parent else PurePosixPath
    return str(flavor(parent) / name)


def historical_basename(value: str) -> str:
    _text(value)
    flavor = PureWindowsPath if _windows(value) or '\\' in value else PurePosixPath
    return flavor(value).name
