"""weights.build_muse_nvfp4_reader: static rules, verify, scale_inventory and verify_pack on fixtures.

Standard library + pytest (+ git for the checkout cases). The runtime cases run only on a host that has the
spike: MUSE_SPIKE_DIR (tiny checkpoints + .venv with torch) and MUSE_SPIKE_TREE (llama.cpp at 9048bad8).
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
sys.path[:0] = [str(CAPSULE / "helpers"), str(HERE)]
import converter_rules  # noqa: E402
import muse_pack_fixture as fx  # noqa: E402
import patchlib  # noqa: E402

FAULTS = {"gate-up-swapped.diff": {"gate_up_mapping"}, "scale2-columns-swapped.diff": {"gate_up_mapping"},
          "input-scale-dropped.diff": {"input_scale_written"}, "eager-repack.diff": {"lazy_repack"},
          "eager-loader.diff": {"lazy_repack"}, "touches-src.diff": {"allowed_paths", "protected_paths"}}
STATIC = "native CC execution"


def call(capability, **inputs):
    proc = subprocess.run([sys.executable, str(CAPSULE / "run.py")], capture_output=True, text=True,
                          input=json.dumps({"capability": capability, "inputs": inputs}))
    assert proc.returncode == 0, proc.stderr
    response = json.loads(proc.stdout)
    assert response["outcome"] == "ok", response
    for c in response["outputs"]["checks"]:
        assert set(c) == {"name", "status", "stage", "detail"}
        assert c["stage"] in {"fixture", "native CC execution", "runtime acceptance"}
    return response["outputs"]


def statuses(out):
    return {c["name"]: c["status"] for c in out["checks"]}


def failed(out):
    return {n for n, s in statuses(out).items() if s == "fail"}


def static_from_text(diff):
    files = patchlib.parse_patch((FIXTURES / diff).read_text(encoding="utf-8"))
    pre = lambda p: (STOCK / p).read_text(encoding="utf-8") if (STOCK / p).is_file() else None  # noqa: E731
    return converter_rules.static_checks(files, patchlib.post_images(files, pre))


# ---- static rules from the diff text alone ---------------------------------------------------------------
def test_good_diff_passes_every_static_rule():
    checks = static_from_text("good.diff")
    assert not [c for c in checks if c["status"] == "fail"], checks
    assert {c["name"] for c in checks if c["status"] == "pass"} >= {
        "allowed_paths", "stacked_reader", "reuses_stock_pack", "lazy_repack", "separate_gate_up_scales",
        "gate_up_mapping", "scale_tensors_written", "input_scale_written"}


@pytest.mark.parametrize("diff,expected", sorted(FAULTS.items()))
def test_each_planted_fault_fails_its_rule(diff, expected):
    bad = {c["name"] for c in static_from_text(diff) if c["status"] == "fail"}
    assert expected <= bad, (diff, bad)


def test_eager_loader_outside_deferred_code_fails_lazy_repack():
    checks = {c["name"]: c for c in static_from_text("eager-loader.diff")}
    assert checks["lazy_repack"]["status"] == "fail" and "to_eager(w_fn())" in checks["lazy_repack"]["detail"]
    good = (FIXTURES / "good.diff").read_text(encoding="utf-8")
    files = patchlib.parse_patch(good)
    post = patchlib.post_images(files, lambda p: (STOCK / p).read_text(encoding="utf-8"))
    path = "conversion/muse_spark.py"
    for bypass in ("            _probe = w_fn().numpy()\n", "            _probe = s_fn()\n",
                   "            _probe = self.model_tensors[name + \"_weight_scale\"]().numpy()\n"):
        edited = dict(post, **{path: post[path].replace("            n_exp, n_out, n_packed = w_fn().shape",
                                                        bypass + "            n_exp, n_out, n_packed = w_fn().shape")})
        status = {c["name"]: c["status"] for c in converter_rules.static_checks(files, edited)}
        assert status["lazy_repack"] == "fail", bypass
    # the small scale_2 / input_scale vectors may stay eager (good.diff loads them when the method runs)
    assert {c["name"]: c["status"] for c in converter_rules.static_checks(files, post)}["lazy_repack"] == "pass"


def test_mapping_written_as_five_tuples_is_inconclusive():
    status = {c["name"]: c["status"] for c in static_from_text("mapping-inconclusive.diff")}
    assert status["gate_up_mapping"] == "inconclusive" and "fail" not in status.values()


def test_unrecognized_split_is_inconclusive_not_pass():
    text = (FIXTURES / "good.diff").read_text(encoding="utf-8")
    files = patchlib.parse_patch(text)
    post = patchlib.post_images(files, lambda p: (STOCK / p).read_text(encoding="utf-8"))
    path = "conversion/muse_spark.py"
    post[path] = post[path].replace("(gguf.MODEL_TENSOR.FFN_GATE_EXP, 0, n_out // 2, 0)",
                                    "(gguf.MODEL_TENSOR.FFN_GATE_EXP, 0, n_out // 2, cols[0])")
    status = {c["name"]: c["status"] for c in converter_rules.static_checks(files, post)}
    assert status["gate_up_mapping"] == "inconclusive"


def test_patch_applier_rebuilds_the_post_image():
    files = patchlib.parse_patch((FIXTURES / "good.diff").read_text(encoding="utf-8"))
    post = patchlib.post_images(files, lambda p: (STOCK / p).read_text(encoding="utf-8"))["conversion/muse_spark.py"]
    assert "def _generate_nvfp4_tensors(self):" in post and post.count("import numpy as np") == 1
    with pytest.raises(patchlib.PatchError):
        patchlib.post_images(files, lambda p: "unrelated\n")


# ---- verify through run.py against a git checkout ---------------------------------------------------------
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


def test_verify_without_runtime_inputs_is_not_done_at_runtime_acceptance(checkout):
    # runtime acceptance is the default bar: without a tiny checkpoint the round trip fails, it is not skipped
    out = call("verify", checkout=str(checkout), diff_path=str(FIXTURES / "good.diff"), python=sys.executable)
    st = statuses(out)
    assert not out["done"] and st["tiny_conversion"] == "fail", out["checks"]
    assert st["fixture_calibration"] == "pass" and st["lazy_repack"] == "pass"
    assert out["stage_reached"] == STATIC


def test_verify_good_diff_static_stage_when_asked(checkout):
    out = call("verify", checkout=str(checkout), diff_path=str(FIXTURES / "good.diff"), require_stage=STATIC)
    st = statuses(out)
    assert out["done"] and out["stage_reached"] == STATIC, out
    assert st["tiny_conversion"] == "skipped"
    bogus = call("verify", checkout=str(checkout), diff_path=str(FIXTURES / "good.diff"), require_stage="x")
    assert not bogus["done"] and failed(bogus) == {"verification_input"}


def test_inconclusive_mapping_is_not_a_pass_without_runtime(checkout):
    diff = str(FIXTURES / "mapping-inconclusive.diff")
    out = call("verify", checkout=str(checkout), diff_path=diff, require_stage=STATIC)
    assert statuses(out)["gate_up_mapping"] == "inconclusive"
    assert not out["done"] and any("inconclusive" in w for w in out["not_done_because"]), out
    out = call("verify", checkout=str(checkout), diff_path=diff)
    assert not out["done"] and statuses(out)["tiny_conversion"] == "fail"


def test_verify_working_tree_change_without_diff_path(checkout):
    files = patchlib.parse_patch((FIXTURES / "good.diff").read_text(encoding="utf-8"))
    post = patchlib.post_images(files, lambda p: (STOCK / p).read_text(encoding="utf-8"))
    (checkout / "conversion/muse_spark.py").write_text(post["conversion/muse_spark.py"], encoding="utf-8", newline="\n")
    out = call("verify", checkout=str(checkout), require_stage=STATIC)
    assert out["done"], out["checks"]
    assert "working change" in next(c["detail"] for c in out["checks"] if c["name"] == "patch_input")


def git_in(root, *args):
    return subprocess.run(["git", "-C", str(root), "-c", "user.name=f", "-c", "user.email=f@example.invalid", *args],
                          check=True, capture_output=True).stdout


def test_an_earlier_nodes_change_is_carried_not_reviewed(checkout, tmp_path):
    # the wiring node's graph edit sits uncommitted in the same checkout
    model = checkout / "src/models/muse-spark.cpp"
    model.write_bytes(model.read_bytes() + b"// graph edit of the earlier node\n")
    carried = tmp_path / "wiring.diff"
    carried.write_bytes(git_in(checkout, "diff", "HEAD", "--", "src/models/muse-spark.cpp"))
    files = patchlib.parse_patch((FIXTURES / "good.diff").read_text(encoding="utf-8"))
    post = patchlib.post_images(files, lambda p: (STOCK / p).read_text(encoding="utf-8"))
    (checkout / "conversion/muse_spark.py").write_text(post["conversion/muse_spark.py"], encoding="utf-8", newline="\n")
    out = call("verify", checkout=str(checkout), require_stage=STATIC)
    assert not out["done"] and "allowed_paths" in failed(out)
    out = call("verify", checkout=str(checkout), require_stage=STATIC, carried_diff=str(carried))
    assert out["done"], out["checks"]
    assert "carried from the earlier node" in next(c["detail"] for c in out["checks"] if c["name"] == "patch_input")
    # committing the earlier change does the same (it is then in the base)
    git_in(checkout, "commit", "-qm", "wiring", "--", "src/models/muse-spark.cpp")
    assert call("verify", checkout=str(checkout), require_stage=STATIC)["done"]
    out = call("verify", checkout=str(checkout), require_stage=STATIC, base="HEAD~1")
    assert "allowed_paths" in failed(out)


@pytest.mark.parametrize("diff,expected", sorted(FAULTS.items()))
def test_verify_rejects_planted_faults(checkout, diff, expected):
    out = call("verify", checkout=str(checkout), diff_path=str(FIXTURES / diff), require_stage=STATIC)
    assert not out["done"] and expected <= failed(out)


def test_verify_without_change_fails(checkout):
    out = call("verify", checkout=str(checkout))
    assert not out["done"] and failed(out) == {"patch_input"}


# ---- scale_inventory on real Muse headers -----------------------------------------------------------------
def test_scale_inventory_on_real_headers(tmp_path):
    ck = FIXTURES / "checkpoint"
    out_path = tmp_path / "inventory.json"
    out = call("scale_inventory", index=str(ck / "model.safetensors.index.json"), headers=[str(ck)], out=str(out_path))
    assert out["done"], out["checks"]
    inv = out["inventory"]
    assert inv["quantized_layers"] == [1, 5, 49] and inv["excluded_layers"] == [0, 61]
    assert inv["roles"]["gate_up.global_scale"] == {"F32 [256, 2]": 1}
    assert inv["roles"]["gate_up.packed_weight"] == {"U8 [256, 8192, 2048]": 2}
    assert inv["roles"]["down.block_scale"] == {"F8_E4M3 [256, 4096, 256]": 2}
    assert any("column 0" in f for f in inv["findings"])
    assert json.loads(out_path.read_text())["experts"]["5"]["gate_up"]["global_scale"]["shape"] == [256, 2]


# ---- verify_pack on synthetic packs ----------------------------------------------------------------------
@pytest.fixture
def ckpt(tmp_path):
    return fx.make_checkpoint(tmp_path / "ckpt")


def test_verify_pack_clean_against_the_checkpoint_and_manifest(tmp_path, ckpt):
    paths = fx.make_pack(tmp_path / "pack")
    inv = fx.make_inventory(tmp_path / "inv.json")
    out = call("verify_pack", pack=str(paths[0]), source_index=str(ckpt), inventory=str(inv), hash=True,
               expect_bytes_range=[1, 1 << 30])
    assert out["done"], out["checks"]
    assert statuses(out)["scale_values"] == "pass" and out["stage_reached"] == STATIC
    m = out["manifest"]
    assert m["format"] == "factory.pack-manifest/1" and m["hashed"] and m["census_by_type"]["nvfp4"] == 6
    assert len(m["files"]) == 2


@pytest.mark.parametrize("kw,expected", [
    ({"drop": ("blk.1.ffn_up_exps.scale",)}, {"expert_scales"}),
    ({"overrides": {"blk.2.ffn_down_exps.weight": "bf16"}}, {"expert_types"}),
    ({"overrides": {"blk.0.ffn_gate_exps.weight": "nvfp4"}}, {"excluded_layers_kept"}),
    ({"overrides": {"blk.0.ffn_up_exps.weight": "f32"}}, {"excluded_layers_kept"}),
    ({"overrides": {"blk.1.attn_q.weight": "nvfp4"}}, {"nvfp4_only_on_experts"}),
    ({"overrides": {"blk.1.attn_q.weight": "q8_0"}}, {"tensor_types"}),
    ({"drop": ("blk.2.ffn_gate_exps.input_scale",)}, {"input_scales"}),
    ({"bad_scale": "blk.1.ffn_gate_exps.scale"}, {"expert_scales", "scale_values"}),
    ({"drop": ("blk.3.ffn_down_exps.weight",)}, {"expert_layers_complete"}),
    ({"swap_columns": True}, {"scale_values"}),
])
def test_verify_pack_planted_faults(tmp_path, ckpt, kw, expected):
    paths = fx.make_pack(tmp_path / "pack", **kw)
    out = call("verify_pack", pack=str(paths[0]), source_index=str(ckpt))
    assert not out["done"] and expected <= failed(out), out["checks"]


def test_verify_pack_catches_swapped_gate_up_columns(tmp_path, ckpt):
    paths = fx.make_pack(tmp_path / "pack", swap_columns=True)
    out = call("verify_pack", pack=str(paths[0]), source_index=str(ckpt))
    detail = next(c["detail"] for c in out["checks"] if c["name"] == "scale_values")
    assert "columns swapped" in " ".join(detail), detail
    assert statuses(out)["expert_scales"] == "pass"  # shape and sign alone cannot see it


def test_verify_pack_rejects_an_empty_plan(tmp_path):
    # the stock converter's all-BF16 pack against a checkpoint read as all-BF16: nothing quantized
    index = fx.make_checkpoint(tmp_path / "ckpt", quantized=())
    overrides = {f"blk.{l}.ffn_{k}_exps.weight": "bf16" for l in fx.QUANTIZED for k in ("gate", "up", "down")}
    drop = tuple(f"blk.{l}.ffn_{k}_exps.{s}" for l in fx.QUANTIZED for k in ("gate", "up", "down")
                 for s in ("scale", "input_scale"))
    paths = fx.make_pack(tmp_path / "pack", overrides=overrides, drop=drop)
    out = call("verify_pack", pack=str(paths[0]), source_index=str(index))
    assert not out["done"] and {"layer_plan", "expert_types", "expert_scales"} <= failed(out), out["checks"]


def test_verify_pack_does_not_trust_an_agent_inventory(tmp_path, ckpt):
    paths = fx.make_pack(tmp_path / "pack")
    inv = tmp_path / "inv.json"
    inv.write_text(json.dumps({"quantized_layers": [], "excluded_layers": [0, 1, 2, 3]}))
    out = call("verify_pack", pack=str(paths[0]), source_index=str(ckpt), inventory=str(inv))
    assert "layer_plan" in failed(out)
    out = call("verify_pack", pack=str(paths[0]), source_index=str(ckpt), quantized_layers=[1])
    assert "layer_plan" in failed(out)


def test_verify_pack_fails_closed(tmp_path, ckpt):
    paths = fx.make_pack(tmp_path / "pack")
    out = call("verify_pack", pack=str(paths[0]), inventory=str(fx.make_inventory(tmp_path / "inv.json")))
    assert not out["done"] and failed(out) == {"verification_input"}  # source_index is required
    out = call("verify_pack", pack=str(paths[0]), source_index=str(tmp_path / "missing.json"))
    assert not out["done"] and {"layer_plan", "expert_types", "expert_scales"} <= failed(out)
    header_only = tmp_path / "hdr"
    header_only.mkdir()
    (header_only / "model.safetensors.index.json").write_bytes(ckpt.read_bytes())
    out = call("verify_pack", pack=str(paths[0]), source_index=str(header_only / "model.safetensors.index.json"))
    assert "scale_values" in failed(out)  # shard data is needed for the values
    paths[1].unlink()
    out = call("verify_pack", pack=str(paths[0]), source_index=str(ckpt))
    assert not out["done"] and failed(out) == {"pack_readable"}
    data = paths[0].read_bytes()
    paths[0].write_bytes(data[:40])
    out = call("verify_pack", pack=str(tmp_path / "pack"), source_index=str(ckpt))
    assert failed(out) == {"pack_readable"}


def test_verify_pack_out_of_range_bytes(tmp_path, ckpt):
    paths = fx.make_pack(tmp_path / "pack")
    out = call("verify_pack", pack=str(paths[0]), source_index=str(ckpt), expect_bytes_range=[1, 100])
    assert failed(out) == {"total_bytes"}


# ---- runtime on the spike host ---------------------------------------------------------------------------
SPIKE = os.environ.get("MUSE_SPIKE_DIR")
TREE = os.environ.get("MUSE_SPIKE_TREE")
runtime = pytest.mark.skipif(not (SPIKE and TREE), reason="set MUSE_SPIKE_DIR and MUSE_SPIKE_TREE on the Spark")


@runtime
@pytest.mark.parametrize("diff,bad", [("good.diff", set()), ("scale2-columns-swapped.diff", {"expert_scales"}),
                                      ("gate-up-swapped.diff", {"blocks_bit_exact", "expert_scales"}),
                                      ("mapping-inconclusive.diff", {"expert_scales"})])
def test_runtime_on_tiny_checkpoint(tmp_path, diff, bad):
    out = call("verify", checkout=TREE, diff_path=str(FIXTURES / diff), python=str(Path(SPIKE) / ".venv/bin/python"),
               tiny_checkpoint=str(Path(SPIKE) / "nvfp4"), work_dir=str(tmp_path))
    runtime_checks = {c["name"]: c["status"] for c in out["checks"] if c["stage"] == "runtime acceptance"}
    assert runtime_checks.get("tiny_conversion") == "pass"
    assert bad <= {n for n, s in runtime_checks.items() if s == "fail"}
    if not bad:
        assert out["done"] and runtime_checks["blocks_bit_exact"] == "pass" and runtime_checks["effective_weights"] == "pass"
        assert out["stage_reached"] == "runtime acceptance"
    else:
        assert not out["done"]
