"""Private local observer helper. Operator credentials remain in its container."""
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from benchmarks.harbor_suite.deployment import operator, staged


def main():
    try:
        request = json.load(sys.stdin)
        value,config,_ = staged(request["workspace"])
        api = operator()
        if request["action"] == "runner":
            args = request["args"]
            if not args or args[0] not in {"run","resume","cancel"}:
                raise ValueError("unsupported runner operation")
            result = api.Transport(config).request("runner",args=args)
        elif request["action"] == "fetch":
            import argparse
            output = api.host.checked(request["output"])
            if output.parent != Path(value["workspace"])/"snapshots":
                raise ValueError("fetch must stay in the protected snapshot workspace")
            result = api.fetch(config,argparse.Namespace(campaign=request["campaign"],output=output))
        else:
            raise ValueError("unsupported transport action")
        print(json.dumps({"ok":True,"result":result}))
        return 0
    except Exception as error:
        print(json.dumps({"ok":False,"error_type":type(error).__name__}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
