"""engine.build_expert_fill: static rules, verify (static stages) and the run parsers on fixtures.

Standard library + pytest (+ git for the checkout cases). The full build-and-run case runs only on a host with
EXPERT_FILL_TREE (a llama.cpp checkout at 9048bad8) and EXPERT_FILL_TINY_DIR (holding tiny-q2exps.gguf), and
optionally EXPERT_FILL_STOCK_BIN (stock llama-simple and llama-perplexity of the same commit).
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

HERE = Path(__file__).resolve().parent
CAPSULE = HERE.parent
FIXTURES = HERE / "fixtures"
STOCK = FIXTURES / "stock"
sys.path.insert(0, str(CAPSULE / "helpers"))
import fill_rules  # noqa: E402
import fill_runs  # noqa: E402
import patchlib  # noqa: E402

FAULTS = {"gate-default-on.diff": {"gate_default_off"}, "fill-after-matmul.diff": {"fill_before_matmul"},
          "fill-writes-tensor.diff": {"no_tensor_writes"}, "touches-ggml-cpu.diff": {"allowed_paths", "protected_paths"}}
STATIC = "native CC execution"


def call(**inputs):
    proc = subprocess.run([sys.executable, str(CAPSULE / "run.py")], capture_output=True, text=True,
                          input=json.dumps({"capability": "verify", "inputs": inputs}))
    assert proc.returncode == 0, proc.stderr
    response = json.loads(proc.stdout)
    assert response["outcome"] == "ok", response
    for c in response["outputs"]["checks"]:
        assert set(c) == {"name", "status", "stage", "detail"}
        assert c["stage"] in {"fixture", "native CC execution", "compile", "runtime acceptance"}
    return response["outputs"]


def failed(out):
    return {c["name"] for c in out["checks"] if c["status"] == "fail"}


def static(diff_text):
    files = patchlib.parse_patch(diff_text)
    patchlib.post_images(files, lambda p: (STOCK / p).read_text(encoding="utf-8") if (STOCK / p).is_file() else None)
    return fill_rules.fill_checks(files)


def statuses(checks):
    return {c["name"]: c["status"] for c in checks}


# ---- static rules from the diff text alone ---------------------------------------------------------------
def test_good_diff_passes_every_rule_cleanly():
    checks = static((FIXTURES / "good.diff").read_text(encoding="utf-8"))
    assert all(c["status"] == "pass" for c in checks), checks


@pytest.mark.parametrize("diff,expected", sorted(FAULTS.items()))
def test_each_planted_fault_fails_its_rule(diff, expected):
    bad = {c["name"] for c in static((FIXTURES / diff).read_text(encoding="utf-8")) if c["status"] == "fail"}
    assert expected <= bad, (diff, bad)


@pytest.mark.parametrize("code,state", [
    ('enabled = env_long("LLAMA_EXPERT_FILL", 0, 0, 1) == 1;', "off"),
    ('enabled = env_flag("LLAMA_EXPERT_FILL", true);', "on"),
    ('const char * e = getenv("LLAMA_EXPERT_FILL"); bool on = e && atoi(e) == 1;', "off"),
    ('const char * e = std::getenv("LLAMA_EXPERT_FILL"); bool on = !e || atoi(e) != 0;', "on"),
    ('const char * e = getenv("LLAMA_EXPERT_FILL"); bool on = e == nullptr || strcmp(e, "0");', "on"),
    ('bool on = getenv("LLAMA_EXPERT_FILL") && strcmp(getenv("LLAMA_EXPERT_FILL"), "1") == 0;', "off"),
    ('bool on = read_gate();', None),
])
def test_gate_default_forms(code, state):
    assert fill_rules.gate_default(code)[0] == state


def test_unrecognized_trigger_is_inconclusive_not_pass():
    good = (FIXTURES / "good.diff").read_text(encoding="utf-8")
    odd = good.replace('"ffn_moe_topk-"', 'kRouterNode').replace('std::strlen("ffn_moe_topk-")', 'std::strlen(kRouterNode)')
    assert statuses(static(odd))["fill_before_matmul"] == "inconclusive"


def test_graph_op_in_the_fill_is_caught():
    good = (FIXTURES / "good.diff").read_text(encoding="utf-8")
    anchor = "+    expert_fill->fill(ranges);\n"
    bad = good.replace(anchor, anchor + "+    ggml_scale_inplace(nullptr, nullptr, 1.0f);\n").replace(
        "@@ -3156,6 +3185,60 @@", "@@ -3156,6 +3185,61 @@")
    assert statuses(static(bad))["no_graph_change"] == "fail"


def test_stats_and_marker_parse():
    err = ("llama_context: n_ctx = 36\nexpert_fill: active threads=8 chunk_kib=1024 max_tokens=1 skip_resident=1\n"
           "0.02.7 I expert_fill: stats calls=124 ranges=1488 bytes_read=0 reads=0 read_errors=0 fill_us=1018\n")
    assert len(fill_runs.markers(err)) == 1
    assert fill_runs.stats(err) == {"calls": 124, "ranges": 1488, "bytes_read": 0, "reads": 0, "read_errors": 0,
                                    "fill_us": 1018}
    assert fill_runs.stats("nothing here") is None
    assert fill_runs.PPL.search("0.02 I Final estimate: PPL = 205577.2103 +/- 2365.38096").group(1) == "205577.2103"


# ---- verify through run.py against a git checkout (static stages) -----------------------------------------
@pytest.fixture
def checkout(tmp_path):
    if not shutil.which("git"):
        pytest.skip("git not available")
    root = tmp_path / "llama.cpp"
    shutil.copytree(STOCK, root)
    git = lambda *a: subprocess.run(["git", "-C", str(root), *a], check=True, capture_output=True)  # noqa: E731
    git("init", "-q", "--template=")
    git("-c", "core.autocrlf=false", "add", "-A")
    git("-c", "user.name=fixture", "-c", "user.email=fixture@example.invalid", "commit", "-qm", "stock")
    return root


def test_verify_good_static_only(checkout):
    out = call(checkout=str(checkout), diff_path=str(FIXTURES / "good.diff"), build=False, require_stage=STATIC)
    st = {c["name"]: (c["status"], c["stage"]) for c in out["checks"]}
    assert out["done"] and out["stage_reached"] == STATIC, out["checks"]
    assert st["fixture_calibration"] == ("pass", "fixture")
    assert st["compile"][0] == "skipped" and st["runtime_acceptance"][0] == "skipped"


def test_skipped_compile_and_runtime_are_not_done_at_runtime_acceptance(checkout):
    out = call(checkout=str(checkout), diff_path=str(FIXTURES / "good.diff"), build=False)
    assert not out["done"] and out["stage_reached"] == STATIC
    assert any("skipped but needed" in w for w in out["not_done_because"]), out["not_done_because"]


@pytest.mark.parametrize("diff,expected", sorted(FAULTS.items()))
def test_verify_rejects_planted_faults(checkout, diff, expected):
    out = call(checkout=str(checkout), diff_path=str(FIXTURES / diff))
    assert not out["done"] and expected <= failed(out)
    assert statuses(out["checks"])["compile"] == "skipped"


def test_verify_working_tree_change(checkout):
    files = patchlib.parse_patch((FIXTURES / "good.diff").read_text(encoding="utf-8"))
    post = patchlib.post_images(files, lambda p: (STOCK / p).read_text(encoding="utf-8") if (STOCK / p).is_file() else None)
    for path, text in post.items():
        (checkout / path).write_text(text, encoding="utf-8", newline="\n")
    out = call(checkout=str(checkout), build=False, require_stage=STATIC)
    assert out["done"], out["checks"]


def test_no_change_is_a_failed_input(checkout):
    out = call(checkout=str(checkout), build=False, require_stage=STATIC)
    assert not out["done"] and "patch_input" in failed(out)


# ---- full build and runtime acceptance (Spark only) ---------------------------------------------------------
TREE, TINY = os.environ.get("EXPERT_FILL_TREE"), os.environ.get("EXPERT_FILL_TINY_DIR")


@pytest.mark.skipif(not (TREE and TINY), reason="set EXPERT_FILL_TREE and EXPERT_FILL_TINY_DIR on the Spark")
@pytest.mark.parametrize("diff,bad", [("good.diff", set()), ("gate-default-on.diff", {"marker_only_with_gate"})])
def test_runtime_acceptance_on_tiny_pack(tmp_path, diff, bad):
    extra = {"stock_bin": os.environ["EXPERT_FILL_STOCK_BIN"]} if os.environ.get("EXPERT_FILL_STOCK_BIN") else {}
    out = call(checkout=TREE, diff_path=str(FIXTURES / diff), tiny_dir=TINY, work_dir=str(tmp_path), jobs=8,
               runtime_even_if_static_fails=bool(bad), **extra)
    if not bad:
        assert out["done"] and out["stage_reached"] == "runtime acceptance", out
    else:
        assert not out["done"] and bad <= failed(out), out
