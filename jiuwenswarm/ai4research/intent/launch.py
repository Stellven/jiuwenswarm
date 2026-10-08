"""Launch the authenticated native intent slice using the existing application."""
import argparse
import os
import secrets
import threading
import time
import urllib.request
import webbrowser


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-browser", action="store_true", help="Container/headless native application launch")
    args = parser.parse_args()
    from jiuwenswarm.codex_start import configure_profile
    from jiuwenswarm.common.utils import prepare_workspace
    from jiuwenswarm.start_services import _run
    profile = configure_profile()
    token = os.environ.get("JIUWENSWARM_DESKTOP_TOKEN")
    if token and len(token) < 32:
        raise RuntimeError("INTENT_AUTH_REQUIRED")
    token = token or secrets.token_urlsafe(48)
    os.environ["JIUWENSWARM_DESKTOP_TOKEN"] = token
    os.environ["JIUWENSWARM_INTENT_TOKEN"] = token
    prepare_workspace(overwrite=False, workspace_dir=profile)
    if not args.no_browser:
        port = int(os.environ.get("FRONTEND_PORT", "5173"))
        def open_native():
            for _ in range(120):
                try:
                    # Check listener only; never send/log the credential in polling.
                    with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=1):
                        pass
                except Exception:
                    time.sleep(1)
                    continue
                webbrowser.open(f"http://127.0.0.1:{port}/?dt={token}")
                return
        threading.Thread(target=open_native, daemon=True).start()
    raise SystemExit(_run("all"))


if __name__ == "__main__":
    main()
