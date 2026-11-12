"""Lightweight guard against configuration for the removed M1 runtime."""

import os
import sys


class LegacyConfigError(ValueError):
    """A launch refers to the removed M1 pipeline."""


def check_legacy_config(environ=os.environ, argv=None) -> None:
    """Reject nonempty M1 settings and the removed research subcommand."""
    for key, value in environ.items():
        if value and (key.startswith("JIUWENSWARM_M1_")
                      or key == "AI4R_PILOT_BUDGET_DIRECTORY"):
            raise LegacyConfigError(_message(key))
    args = sys.argv[1:] if argv is None else argv
    positional = [a for a in args if not a.startswith("-")]
    # Only the removed `research` *subcommand* (first positional) is legacy; the word
    # elsewhere (a prompt, a path) is ordinary input.
    if positional[:1] == ["research"]:
        raise LegacyConfigError(_message("research"))


def _message(key):
    return (f"Legacy configuration {key}: the M1 pipeline was removed on this branch. "
            "See docs/architecture/factory/MIGRATION.md.")


def check_legacy_config_or_exit() -> None:
    """CLI boundary: report an actionable error before any service imports."""
    try:
        check_legacy_config()
    except LegacyConfigError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(2) from None
