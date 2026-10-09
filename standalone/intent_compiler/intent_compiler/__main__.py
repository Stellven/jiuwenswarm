"""One entrypoint starts the built UI, API and server-owned compiler runtime."""

import argparse
import os
import sys


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "serve":
        parser = argparse.ArgumentParser(description=__doc__)
        parser.add_argument("operation")
        parser.add_argument("--host", default=os.getenv("INTENT_HOST", "127.0.0.1"))
        parser.add_argument("--port", type=int, default=int(os.getenv("PORT", "5173")))
        args = parser.parse_args()
        allowed = {"127.0.0.1", "::1", "localhost"}
        if os.getenv("INTENT_CONTAINER") == "1":
            allowed.add("0.0.0.0")
        if args.host not in allowed:
            parser.error("Use loopback locally; container forwarding requires INTENT_CONTAINER=1")
        from .config import Config
        from .api import create_app
        import uvicorn
        uvicorn.run(create_app(Config.from_env()), host=args.host, port=args.port, access_log=False)
    else:
        from .client import cli
        raise SystemExit(cli())


if __name__ == "__main__":
    main()
