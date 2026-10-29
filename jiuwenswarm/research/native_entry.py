"""Fixed unprivileged native process roles, with logging before native imports."""
from __future__ import annotations
import os
import runpy
import sys
from pathlib import Path

MODULES = {"agentserver": "jiuwenswarm.server.app_agentserver",
           "gateway": "jiuwenswarm.gateway.app_gateway",
           "frontend": "jiuwenswarm.channels.web.app_web"}


def main(argv=None):
    arguments = list(sys.argv[1:] if argv is None else argv)
    if len(arguments) != 1 or arguments[0] not in MODULES:
        raise SystemExit("A fixed native role is required")
    if os.environ.get("JIUWENSWARM_M1_PROFILE") != "1" or os.geteuid() != 10001:
        raise SystemExit("Protected native process identity required")
    role = arguments[0]
    from .native_logging import configure_native_logging
    configure_native_logging(Path(os.environ["JIUWENSWARM_DATA_DIR"]) / "logs" / role)
    capture = role == "gateway"
    if capture:
        from .trajectory import start_native_capture
        start_native_capture(Path(os.environ["JIUWENSWARM_DATA_DIR"]) / "trajectory" / role)
    sys.argv = [MODULES[role]]
    try:
        runpy.run_module(MODULES[role], run_name="__main__", alter_sys=True)
    finally:
        if capture:
            from .trajectory import stop_native_capture
            stop_native_capture()


if __name__ == "__main__":
    main()
