"""Staged local subscription launcher: python -m jiuwenswarm.codex_start.

Uses a new profile; never imports, resets or deletes the old installation.
"""
import os
import argparse
import logging
import sys
from pathlib import Path


def configure_profile():
    profile = (Path.home() / ".jiuwenswarm-ai4r").resolve()
    profile.mkdir(parents=True, exist_ok=True)
    marker = profile / ".ai4r-subscription-profile"
    if not marker.exists():
        if any(profile.iterdir()):
            raise RuntimeError("The subscription profile directory is not empty and has no AI4R marker.")
        marker.write_text("1\n", encoding="utf-8")
    os.environ["JIUWENSWARM_DATA_DIR"] = str(profile)
    os.environ["JIUWENSWARM_AGENT_SDK"] = "codex_subscription"
    for name in ("GATEWAY_HOST", "WEB_HOST", "AGENT_SERVER_HOST"):
        os.environ[name] = "127.0.0.1"
    return profile


def main():
    parser = argparse.ArgumentParser(description="Start the local AI4R subscription preview in its own profile.")
    parser.add_argument("mode", nargs="?", default="all", choices=["all", "web", "app"])
    args = parser.parse_args()
    profile = configure_profile()
    from jiuwenswarm.common.utils import prepare_workspace
    prepare_workspace(overwrite=False, workspace_dir=profile)
    from jiuwenswarm.start_services import _run
    logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stdout)
    raise SystemExit(_run(args.mode))


if __name__ == "__main__":
    main()
