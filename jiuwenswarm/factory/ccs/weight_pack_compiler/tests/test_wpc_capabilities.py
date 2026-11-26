"""Weight pack compiler capsule: every capability on tiny synthetic GGUF packs, clean and with planted faults.

Standard library plus pytest; each call goes through run.py with the ccv2 stdin/stdout packet.
"""
import json
from pathlib import Path
import subprocess
import sys

import pytest

HERE = Path(__file__).resolve().parent
CAPSULE = HERE.parent
sys.path.insert(0, str(HERE))
import wpc_gguf_fixture as fx  # noqa: E402


def call(capability, **inputs):
    proc = subprocess.run([sys.executable, str(CAPSULE / "run.py")], capture_output=True, text=True,
                          input=json.dumps({"capability": capability, "inputs": inputs}))
    assert proc.returncode == 0, proc.stderr
    response = json.loads(proc.stdout)
    assert response["outcome"] == "ok", response
    out = response["outputs"]
    for check in out["checks"]:
        assert set(check) == {"name", "status", "stage", "detail"}
        assert check["status"] in {"pass", "fail", "skipped", "inconclusive", "info"}
    return out


def status(out):
    return {c["name"]: c["status"] for c in out["checks"]}


def failed(out):
    return sorted(n for n, s in status(out).items() if s == "fail")


@pytest.fixture
def world(tmp_path):
    src = fx.make_source(tmp_path)
    imatrix = tmp_path / "imatrix.gguf"
    imatrix.write_bytes(b"synthetic importance matrix")
    recipe = tmp_path / "recipe.json"
    out = call("plan_recipe", pack_manifest=str(src[0]), imatrix=str(imatrix), hash=True, recipe_out=str(recipe),
               llama_quantize="/opt/llama.cpp/bin/llama-quantize")
    assert out["done"], out["checks"]
    return {"dir": tmp_path, "src": src, "imatrix": imatrix, "recipe": recipe, "plan": out}


def edit(world, change):
    data = json.loads(world["recipe"].read_text())
    change(data)
    path = world["dir"] / "edited-recipe.json"
    path.write_text(json.dumps(data))
    return str(path)


# ---- plan_recipe -------------------------------------------------------------------------------------------
def test_plan_recipe_pins_every_non_expert_and_targets_experts(world):
    recipe = json.loads(world["recipe"].read_text())
    assert recipe["format"] == "factory.pack-recipe/1"
    argv = recipe["argv"]
    assert argv[1] == "--allow-requantize" and "--keep-split" in argv and argv[-1] == "Q2_K"
    assert argv[argv.index("--imatrix") + 1] == str(world["imatrix"])
    pins = [argv[i + 1] for i, a in enumerate(argv) if a == "--tensor-type"]
    assert "^blk\\.(0|1|2)\\.ffn_down_exps\\.weight$=q2_k" in pins
    assert "^blk\\.(0|1|2)\\.attn_q\\.weight$=q8_0" in pins and "^token_embd\\.weight$=q4_k" in pins
    roles = {t["name"]: (t["source_type"], t["target_type"]) for t in recipe["tensors"]}
    assert roles["blk.1.ffn_up_exps.weight"] == ("nvfp4", "q2_k")
    assert roles["blk.1.ffn_gate_shexp.weight"] == ("nvfp4", "nvfp4")
    assert roles["blk.1.ffn_up_exps.scale"] == ("f32", "f32")
    assert all(len(f["sha256"]) == 64 for f in recipe["source"]["files"])
    # 9 routed tensors of 256*256*4 values: Q2_K is 84 bytes per 256, NVFP4 36 per 64
    q2 = sum(t["target_bytes"] for t in recipe["tensors"] if t["role"] == "routed_expert")
    assert q2 == 9 * (256 * 256 * 4 // 256 * 84)
    assert recipe["estimate"]["temp_peak_bytes"] >= recipe["estimate"]["output_bytes"]
    assert "--prune-layers" in recipe["probe"]["argv"]


def test_plan_recipe_refuses_rows_that_are_not_whole_q2k_blocks(tmp_path):
    src = fx.make_source(tmp_path, n_embd=320)  # 320 = 5 NVFP4 blocks, not whole Q2_K blocks
    out = call("plan_recipe", pack_manifest=str(src[0]), imatrix=str(src[0]), hash=False)
    assert not out["done"] and "block_divisibility" in failed(out)
    assert "stock would write q4_0" in next(c["detail"] for c in out["checks"] if c["name"] == "block_divisibility")


def test_plan_recipe_from_ingest_manifest_and_without_imatrix(tmp_path):
    src = fx.make_source(tmp_path)
    manifest = tmp_path / "nvfp4-manifest.json"
    manifest.write_text(json.dumps({"files": [{"path": p.name, "bytes": p.stat().st_size, "sha256": "a" * 64}
                                              for p in src]}))
    out = call("plan_recipe", pack_manifest=str(manifest))
    assert failed(out) == ["imatrix_named"]
    assert all(f["sha256"] == "a" * 64 for f in out["recipe"]["source"]["files"])


# ---- verify_recipe -----------------------------------------------------------------------------------------
def recipe_check(world, recipe=None, **inputs):
    inputs.setdefault("target", "q2_k")
    inputs.setdefault("pack_manifest", str(world["src"][0]))
    return call("verify_recipe", recipe=str(recipe or world["recipe"]), **inputs)


def test_verify_recipe_clean(world):
    out = recipe_check(world, disk_grant_bytes=1 << 30)
    assert out["done"], out["checks"]
    assert status(out)["argv_realizes_targets"] == "pass" and status(out)["target_matches"] == "pass"


def test_verify_recipe_needs_target_and_source_from_the_caller(world):
    for missing in ("target", "pack_manifest"):
        inputs = {"recipe": str(world["recipe"]), "target": "q2_k", "pack_manifest": str(world["src"][0])}
        del inputs[missing]
        out = call("verify_recipe", **inputs)
        assert not out["done"] and failed(out) == ["verification_input"], (missing, out["checks"])
    out = recipe_check(world, target="q4_k")
    assert not out["done"] and "target_matches" in failed(out)


def _experts_to(type_, target=None):
    def change(r):
        for t in r["tensors"]:
            if t["role"] == "routed_expert":
                t["target_type"] = type_
        if target:
            r["target"] = target
    return change


def test_verify_recipe_requires_experts_to_change_type(world):
    # pinning the routed experts to their source type is not a requantization
    out = recipe_check(world, edit(world, _experts_to("nvfp4", "nvfp4")), target="nvfp4")
    assert not out["done"] and "expert_targets" in failed(out)
    assert "must change" in next(c["detail"] for c in out["checks"] if c["name"] == "expert_targets")
    out = recipe_check(world, edit(world, _experts_to("nvfp4")))
    assert not out["done"] and "expert_targets" in failed(out)


def _lie_about_output(r):
    t = next(t for t in r["tensors"] if t["name"] == "output.weight")
    t["source_type"] = t["target_type"] = "q4_k"  # the source header says q8_0


def test_verify_recipe_does_not_take_the_recipes_word_for_source_types(world):
    out = recipe_check(world, edit(world, _lie_about_output))
    assert not out["done"] and {"source_matches_recipe", "non_expert_kept"} <= set(failed(out)), out["checks"]


def _drop_flag(flag):
    return lambda r: r["argv"].remove(flag)


def _set_target(name, type_):
    def change(r):
        next(t for t in r["tensors"] if t["name"] == name)["target_type"] = type_
    return change


def _drop_pin(fragment):
    def change(r):
        i = next(i for i, a in enumerate(r["argv"]) if fragment in a)
        del r["argv"][i - 1:i + 1]
    return change


def _no_imatrix(r):
    i = r["argv"].index("--imatrix")
    del r["argv"][i:i + 2]
    r["imatrix"] = None


@pytest.mark.parametrize("change,check", [
    (_drop_flag("--allow-requantize"), "allow_requantize"),
    (_set_target("blk.1.ffn_gate_exps.weight", "q4_k"), "expert_targets"),
    (_set_target("blk.2.attn_q.weight", "q4_k"), "non_expert_kept"),
    (_drop_pin("attn_q"), "argv_realizes_targets"),
    (_no_imatrix, "imatrix_named"),
    (lambda r: [f.pop("sha256") for f in r["source"]["files"]], "source_digests"),
    (lambda r: r["argv"].insert(1, "--include-weights-typo"), "argv_parses"),
    (lambda r: r["argv"].__setitem__(slice(1, 1), ["--prune-layers", "2"]), "argv_scope"),
    (lambda r: r["estimate"].__setitem__("output_data_bytes", 1), "estimate_consistent"),
])
def test_verify_recipe_planted_faults(world, change, check):
    out = recipe_check(world, edit(world, change))
    assert not out["done"] and check in failed(out), out["checks"]


def test_verify_recipe_rejects_types_without_gb10_kernel_and_disk_over_grant(world):
    def to_iq1(r):
        for t in r["tensors"]:
            if t["role"] == "routed_expert":
                t["target_type"] = "iq1_s"
    out = recipe_check(world, edit(world, to_iq1), target="iq1_s")
    assert "gb10_kernel_types" in failed(out)
    out = recipe_check(world, disk_grant_bytes=1000)
    assert failed(out) == ["disk_grant"]


def test_verify_recipe_notices_a_different_source(world, tmp_path):
    other = tmp_path / "other"
    other.mkdir()
    src = fx.make_source(other, drop=("blk.1.ffn_up_exps.scale",))
    out = recipe_check(world, pack_manifest=str(src[0]))
    assert "source_matches_recipe" in failed(out)


# ---- verify_pack -------------------------------------------------------------------------------------------
def verify(world, out_dir, **inputs):
    inputs.setdefault("target", "q2_k")
    inputs.setdefault("expect_bytes_range", [1, 1 << 30])
    inputs.setdefault("recipe", str(world["recipe"]))
    inputs.setdefault("source_pack", str(world["src"][0]))
    return call("verify_pack", pack=str(Path(out_dir) / "muse-nvfp4-Q2_K-00001-of-00002.gguf"), **inputs)


def test_verify_pack_clean_and_manifest(world, tmp_path):
    out_dir = tmp_path / "q2"
    out_dir.mkdir()
    fx.make_q2(out_dir)
    out = verify(world, out_dir)
    assert out["done"], out["checks"]
    manifest = out["manifest"]
    assert manifest["format"] == "factory.pack-manifest/1" and not manifest["hashed"]
    assert manifest["census"]["routed_expert"] == {"q2_k": 9}
    assert all("header_sha256" in f and "mtime" in f for f in manifest["files"])
    # a directory works as well as the first shard
    assert call("verify_pack", pack=str(out_dir), recipe=str(world["recipe"]), source_pack=str(world["src"][0]),
                target="q2_k", expect_bytes_range=[1, 1 << 30])["done"]
    # without a recipe the source headers and the caller's target are the whole reference
    assert call("verify_pack", pack=str(out_dir), source_pack=str(world["src"][0]), target="q2_k",
                expect_bytes_range=[1, 1 << 30])["done"]


@pytest.mark.parametrize("plant,check", [
    (dict(overrides={"blk.1.attn_q.weight": "q4_k"}), "non_expert_types"),
    (dict(drop=("blk.2.ffn_down_exps.scale",)), "scale_tensors_present"),
    (dict(scale_shift=0.125), "scale_tensors_identical"),
    (dict(overrides={"blk.2.ffn_up_exps.weight": "nvfp4"}), "expert_types"),
    (dict(imatrix_name=None), "imatrix_recorded"),
])
def test_verify_pack_planted_faults(world, tmp_path, plant, check):
    out_dir = tmp_path / "q2"
    out_dir.mkdir()
    fx.make_q2(out_dir, **plant)
    out = verify(world, out_dir)
    assert not out["done"] and check in failed(out), out["checks"]


def test_verify_pack_missing_shard_fails_closed(world, tmp_path):
    out_dir = tmp_path / "q2"
    out_dir.mkdir()
    paths = fx.make_q2(out_dir)
    paths[1].unlink()
    out = verify(world, out_dir)
    assert failed(out) == ["pack_readable"] and "missing shards" in out["checks"][0]["detail"]


def test_verify_pack_size_range_and_no_reference(world, tmp_path):
    out_dir = tmp_path / "q2"
    out_dir.mkdir()
    fx.make_q2(out_dir)
    assert "total_bytes" in failed(verify(world, out_dir, expect_bytes_range=[250 * 10**9, 320 * 10**9]))
    first = str(out_dir / "muse-nvfp4-Q2_K-00001-of-00002.gguf")
    bare = call("verify_pack", pack=first)  # source_pack, target and expect_bytes_range missing: each fails
    assert not bare["done"] and {"source_readable", "target_given", "total_bytes", "expert_types", "non_expert_types",
                                 "scale_tensors_present"} <= set(failed(bare))


def test_verify_pack_judges_types_against_the_source_not_the_recipe(world, tmp_path):
    out_dir = tmp_path / "q2"
    out_dir.mkdir()
    fx.make_q2(out_dir, overrides={"output.weight": "q4_k"})
    out = verify(world, out_dir, recipe=edit(world, _lie_about_output))
    assert not out["done"] and "non_expert_types" in failed(out), out["checks"]
    assert "output.weight" in next(c["detail"] for c in out["checks"] if c["name"] == "non_expert_types")


def test_verify_pack_target_from_the_caller(world, tmp_path):
    out_dir = tmp_path / "q2"
    out_dir.mkdir()
    fx.make_q2(out_dir)
    out = verify(world, out_dir, target="q4_k")
    assert not out["done"] and {"target_matches", "expert_types"} <= set(failed(out))
    same = tmp_path / "same"
    same.mkdir()
    fx.make_q2(same, expert_type="nvfp4")  # experts left at the source type
    out = verify(world, same, target="nvfp4", recipe=edit(world, _experts_to("nvfp4", "nvfp4")))
    assert not out["done"] and "expert_types" in failed(out)
    assert "not converted" in next(c["detail"] for c in out["checks"] if c["name"] == "expert_types")


def test_verify_pack_rejects_a_corrupt_header(world, tmp_path):
    out_dir = tmp_path / "q2"
    out_dir.mkdir()
    paths = fx.make_q2(out_dir)
    paths[0].write_bytes(paths[0].read_bytes()[:40])
    assert failed(verify(world, out_dir)) == ["pack_readable"]


def test_publish_manifest_writes_hashed_manifest(world, tmp_path):
    out_dir = tmp_path / "q2"
    out_dir.mkdir()
    fx.make_q2(out_dir)
    target = tmp_path / "q2-manifest.json"
    out = call("publish_manifest", pack=str(out_dir), source_pack=str(world["src"][0]),
               recipe=str(world["recipe"]), out=str(target), target="q2_k", expect_bytes_range=[1, 1 << 30])
    assert out["done"] and json.loads(target.read_text())["hashed"] is True
    target.unlink()
    (out_dir / "muse-nvfp4-Q2_K-00002-of-00002.gguf").unlink()
    out = call("publish_manifest", pack=str(out_dir), source_pack=str(world["src"][0]), out=str(target),
               target="q2_k", expect_bytes_range=[1, 1 << 30])
    assert not out["done"] and not target.exists()


def test_unknown_capability_is_an_error():
    proc = subprocess.run([sys.executable, str(CAPSULE / "run.py")], capture_output=True, text=True,
                          input=json.dumps({"capability": "verify", "inputs": {}}))
    assert json.loads(proc.stdout)["outcome"] == "error"


# ---- mixed 2-bit target: base type plus per-projection overrides -------------------------------------------
MIXED = "iq2_xxs,down=q2_k"


def test_plan_and_verify_recipe_with_a_mixed_target(world, tmp_path):
    recipe_path = tmp_path / "mixed-recipe.json"
    out = call("plan_recipe", pack_manifest=str(world["src"][0]), imatrix=str(world["imatrix"]), hash=True,
               recipe_out=str(recipe_path), target="IQ2_XXS, down=Q2_K", llama_quantize="/opt/llama.cpp/bin/llama-quantize")
    assert out["done"], out["checks"]
    recipe = json.loads(recipe_path.read_text())
    assert recipe["target"] == MIXED and recipe["argv"][-1] == "IQ2_XXS"
    assert recipe["roles"]["routed_expert_by_projection"] == {"gate": "iq2_xxs", "up": "iq2_xxs", "down": "q2_k"}
    pins = [recipe["argv"][i + 1] for i, a in enumerate(recipe["argv"]) if a == "--tensor-type"]
    assert "^blk\.(0|1|2)\.ffn_down_exps\.weight$=q2_k" in pins
    assert "^blk\.(0|1|2)\.ffn_gate_exps\.weight$=iq2_xxs" in pins
    routed = sum(t["target_bytes"] for t in recipe["tensors"] if t["role"] == "routed_expert")
    assert routed == 3 * (256 * 256 * 4 // 256 * 84) + 6 * (256 * 256 * 4 // 256 * 66)
    checks = call("verify_recipe", recipe=str(recipe_path), target=MIXED, pack_manifest=str(world["src"][0]))
    assert checks["done"], checks["checks"]
    # the same recipe judged against a uniform target fails: the caller's target is the reference
    uniform = call("verify_recipe", recipe=str(recipe_path), target="iq2_xxs", pack_manifest=str(world["src"][0]))
    assert not uniform["done"] and {"target_matches", "expert_targets"} <= set(failed(uniform))
    bad = call("verify_recipe", recipe=str(recipe_path), target="down=q2_k", pack_manifest=str(world["src"][0]))
    assert not bad["done"] and "target_given" in failed(bad)


def test_verify_pack_with_a_mixed_target(world, tmp_path):
    out_dir = tmp_path / "mixed"
    out_dir.mkdir()
    down = {f"blk.{n}.ffn_down_exps.weight": "q2_k" for n in range(3)}
    fx.make_q2(out_dir, expert_type="iq2_xxs", overrides=down)
    common = dict(pack=str(out_dir), source_pack=str(world["src"][0]), expect_bytes_range=[1, 1 << 30])
    out = call("verify_pack", target=MIXED, **common)
    assert out["done"], out["checks"]
    assert out["manifest"]["census"]["routed_expert"] == {"iq2_xxs": 6, "q2_k": 3}
    wrong = call("verify_pack", target="iq2_xxs", **common)
    assert not wrong["done"] and "expert_types" in failed(wrong)
