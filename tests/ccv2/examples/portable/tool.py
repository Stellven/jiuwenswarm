"""Small standard-library worker shared unchanged by native and image bindings."""
import json
from pathlib import Path
import sys


def main():
    request = json.load(sys.stdin)
    capability = request["capability"]
    inputs = request["inputs"]
    if capability == "trim":
        # Deliberately ASCII-only whitespace, independent of locale/Unicode tables.
        outputs = {"trimmed": inputs["text"].strip(" \t\r\n\v\f")}
    elif capability == "empty":
        outputs = {}
    elif capability == "echo":
        outputs = {"value": inputs["value"]}
    elif capability == "write-text":
        (Path(request["output_dir"]) / "result.txt").write_bytes(inputs["text"].encode("utf-8"))
        outputs = {"file": {"path": "result.txt"}}
    else:
        raise ValueError("unknown capability: " + capability)
    print(json.dumps({"outcome": "ok", "outputs": outputs}, ensure_ascii=True))


if __name__ == "__main__":
    main()
