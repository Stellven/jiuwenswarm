# Synthetic packaging fixture; no runtime result is claimed. Never run.
import json


def measurement_placeholder():
    return {"latency_ms": None, "quality": None}


if __name__ == "__main__":
    print(json.dumps({"metrics": measurement_placeholder()}))
