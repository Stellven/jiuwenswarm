"""Guard that keeps the software factory CLI out of an M1 research profile.

The M1 research runtime and the factory share the repository but not a process:
`jiuwenswarm-factory` refuses to start when M1 profile settings are present.
Shared entry points (chat CLI, start_services, codex_start) are not guarded.
"""

import os
import sys


class LegacyConfigError(ValueError):
    """A factory launch carries M1 research-profile configuration."""


def check_legacy_config(environ=os.environ, argv=None) -> None:
    """Reject nonempty M1 settings and the research subcommand for the factory CLI."""
    for key, value in environ.items():
        if value and (key.startswith("JIUWENSWARM_M1_")
                      or key == "AI4R_PILOT_BUDGET_DIRECTORY"):
            raise LegacyConfigError(_message(key))
    args = sys.argv[1:] if argv is None else argv
    positional = [a for a in args if not a.startswith("-")]
    # Only the `research` *subcommand* (first positional) is legacy; the word
    # elsewhere (a prompt, a path) is ordinary input.
    if positional[:1] == ["research"]:
        raise LegacyConfigError(_message("research"))


def _message(key):
    return (f"Legacy configuration {key}: the software factory does not run under the M1 research profile. "
            "See docs/architecture/factory/MIGRATION.md.")


def check_legacy_config_or_exit() -> None:
    """CLI boundary: report an actionable error before any service imports."""
    try:
        check_legacy_config()
    except LegacyConfigError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(2) from None
