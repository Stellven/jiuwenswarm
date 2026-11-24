"""CC v2 native entry: one JSON packet on stdin, one JSON result on stdout.

Capabilities: plan_recipe (actor helper), verify_recipe and verify_pack (verifiers), publish_manifest (writer).
Pass absolute paths: the host runs this process in its own attempt directory.
"""
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / "helpers"))
from pack_check import load_recipe, verify_pack  # noqa: E402
from recipe import plan_recipe  # noqa: E402
from recipe_check import verify_recipe  # noqa: E402

STAGE = "native CC execution"


def result(checks, **extra):
    done = bool(checks) and all(c["status"] != "fail" for c in checks)
    return {"done": done, "checks": checks, **extra}


def input_error(exc):
    return result([{"name": "verification_input", "status": "fail", "stage": STAGE, "detail": str(exc)}])


def do_plan_recipe(inputs):
    recipe, checks = plan_recipe(
        inputs["pack_manifest"], inputs.get("target", "q2_k"), inputs.get("imatrix"), inputs.get("output"),
        inputs.get("llama_quantize", "llama-quantize"), inputs.get("keep_split"), inputs.get("threads"),
        bool(inputs.get("hash", False)), inputs.get("disk_grant_bytes"), inputs.get("probe_layer"))
    out = inputs.get("recipe_out")
    if out:
        Path(out).write_text(json.dumps(recipe, indent=1) + "\n", encoding="utf-8")
        checks.append({"name": "recipe_written", "status": "pass", "stage": STAGE, "detail": str(out)})
    summary = {k: recipe[k] for k in ("source", "target", "imatrix", "overrides", "output", "argv", "probe", "estimate")}
    return result(checks, recipe=summary)


def do_verify_recipe(inputs):
    recipe = load_recipe(inputs["recipe"])
    return result(verify_recipe(recipe, inputs.get("target"), inputs.get("pack_manifest"),
                                inputs.get("disk_grant_bytes"), inputs.get("gb10_types")))


def do_verify_pack(inputs):
    checks, manifest = verify_pack(inputs["pack"], load_recipe(inputs.get("recipe")), inputs.get("source_pack"),
                                   inputs.get("expect_bytes_range"), inputs.get("target"), bool(inputs.get("hash", False)))
    return result(checks, manifest=manifest)


def do_publish_manifest(inputs):
    checks, manifest = verify_pack(inputs["pack"], load_recipe(inputs.get("recipe")), inputs.get("source_pack"),
                                   inputs.get("expect_bytes_range"), inputs.get("target"), bool(inputs.get("hash", True)))
    if manifest is not None and all(c["status"] != "fail" for c in checks):
        Path(inputs["out"]).write_text(json.dumps(manifest, indent=1) + "\n", encoding="utf-8")
        checks.append({"name": "manifest_written", "status": "pass", "stage": STAGE, "detail": inputs["out"]})
    else:
        checks.append({"name": "manifest_written", "status": "skipped", "stage": STAGE,
                       "detail": "not written: the pack failed verification"})
    return result(checks, manifest=manifest)


CAPABILITIES = {"plan_recipe": do_plan_recipe, "verify_recipe": do_verify_recipe, "verify_pack": do_verify_pack,
                "publish_manifest": do_publish_manifest}


def main():
    packet = json.load(sys.stdin)
    handler = CAPABILITIES.get(packet.get("capability"))
    if handler is None:
        response = {"outcome": "error", "error": {"code": "INVALID_INPUT",
                                                  "message": f"Expected one of {sorted(CAPABILITIES)}"}}
    else:
        try:
            outputs = handler(packet.get("inputs", {}))
        except (KeyError, OSError, TypeError, ValueError) as exc:
            outputs = input_error(f"{type(exc).__name__}: {exc}")
        response = {"outcome": "ok", "outputs": outputs}
    print(json.dumps(response))


if __name__ == "__main__":
    main()
