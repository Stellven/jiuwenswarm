"""weights.build_expert_scale_wiring: static rules, verify (static stages) and the runtime parsers on fixtures.

Standard library + pytest (+ git for the checkout cases). The full build-and-run case runs only on a host with
MUSE_SPIKE_TREE (llama.cpp at 9048bad8) and MUSE_TINY_DIR (tiny-bf16.gguf, tiny-nvfp4-f32.gguf,
tiny-deqref-f32.gguf), and optionally MUSE_STOCK_BIN.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys

import pytest

HERE = Path(__file__).resolve().parent
CAPSULE = HERE.parent
FIXTURES = HERE / "fixtures"
STOCK = FIXTURES / "stock"
sys.path.insert(0, str(CAPSULE / "helpers"))
import kld_compare  # noqa: E402
import patchlib  # noqa: E402
import slice_compare  # noqa: E402
import wiring_rules  # noqa: E402

FAULTS = {"up-gets-gate-scale.diff": {"scale_args"}, "down-scale-missing.diff": {"scale_args"},
          "touches-ggml.diff": {"allowed_paths", "protected_paths"}}
MODEL = "src/models/muse-spark.cpp"
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
    read = lambda p: (STOCK / p).read_text(encoding="utf-8") if (STOCK / p).is_file() else None  # noqa: E731
    post = patchlib.post_images(files, read)
    return wiring_rules.wiring_checks(files, read(MODEL), post.get(MODEL), read("src/llama-graph.h"))


# ---- static rules from the diff text alone ---------------------------------------------------------------
def test_good_diff_binds_each_scale_by_name():
    checks = static((FIXTURES / "good.diff").read_text(encoding="utf-8"))
    assert not [c for c in checks if c["status"] == "fail"], checks
    detail = next(c["detail"] for c in checks if c["name"] == "scale_args")
    assert detail == {"up_exps_s": "model.layers[il].ffn_up_exps_s", "gate_exps_s": "model.layers[il].ffn_gate_exps_s",
                      "down_exps_s": "model.layers[il].ffn_down_exps_s"}


@pytest.mark.parametrize("diff,expected", sorted(FAULTS.items()))
def test_each_planted_fault_fails_its_rule(diff, expected):
    bad = {c["name"] for c in static((FIXTURES / diff).read_text(encoding="utf-8")) if c["status"] == "fail"}
    assert expected <= bad, (diff, bad)


def test_other_argument_moved_and_extra_code_are_caught():
    good = (FIXTURES / "good.diff").read_text(encoding="utf-8")
    moved = good.replace("+                nullptr,\n+                model.layers[il].ffn_up_exps_s,",
                         "+                router_logits,\n+                model.layers[il].ffn_up_exps_s,")
    assert "call_otherwise_unchanged" in {c["name"] for c in static(moved) if c["status"] == "fail"}
    read = lambda p: (STOCK / p).read_text(encoding="utf-8")  # noqa: E731
    files = patchlib.parse_patch(good)
    post = patchlib.post_images(files, read)[MODEL].replace('cb(moe_out, "ffn_moe_out", il);',
                                                            'moe_out = ggml_scale(ctx0, moe_out, 1.0f);\n        cb(moe_out, "ffn_moe_out", il);')
    checks = wiring_rules.wiring_checks(files, read(MODEL), post, read("src/llama-graph.h"))
    assert "edits_confined_to_call" in {c["name"] for c in checks if c["status"] == "fail"}


def test_call_binds_the_overload_by_type_op_position():
    header = (STOCK / "src/llama-graph.h").read_text(encoding="utf-8")
    decls = wiring_rules.declarations(header)
    assert [len(d) for d in decls] == [21, 26]
    args = wiring_rules.calls((STOCK / MODEL).read_text(encoding="utf-8"))[0][2]
    assert wiring_rules.resolve(decls, args) == decls[0]


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
    assert st["fixture_calibration"] == ("pass", "fixture") and st["scale_args"][0] == "pass"
    assert st["compile"][0] == "skipped" and st["runtime_acceptance"][0] == "skipped"
    assert not any(c["status"] == "pass" and c["stage"] in ("compile", "runtime acceptance") for c in out["checks"])


@pytest.mark.parametrize("diff,expected", sorted(FAULTS.items()))
def test_verify_rejects_planted_faults(checkout, diff, expected):
    out = call(checkout=str(checkout), diff_path=str(FIXTURES / diff))
    assert not out["done"] and expected <= failed(out)
    assert {c["name"]: c["status"] for c in out["checks"]}["compile"] == "skipped"


def test_verify_working_tree_change(checkout):
    files = patchlib.parse_patch((FIXTURES / "good.diff").read_text(encoding="utf-8"))
    post = patchlib.post_images(files, lambda p: (STOCK / p).read_text(encoding="utf-8"))
    (checkout / MODEL).write_text(post[MODEL], encoding="utf-8", newline="\n")
    out = call(checkout=str(checkout), build=False, require_stage=STATIC)
    assert out["done"], out["checks"]


def test_skipped_compile_and_runtime_are_not_done_at_runtime_acceptance(checkout):
    out = call(checkout=str(checkout), diff_path=str(FIXTURES / "good.diff"), build=False)
    assert not out["done"] and out["stage_reached"] == STATIC
    assert any("skipped but needed" in w for w in out["not_done_because"]), out["not_done_because"]


def test_scale_args_tolerate_whitespace_inside_the_member_expression():
    good = (FIXTURES / "good.diff").read_text(encoding="utf-8")
    spaced = good.replace("+                model.layers[il].ffn_up_exps_s,", "+                model.layers[il] .ffn_up_exps_s,")
    assert {c["name"]: c["status"] for c in static(spaced)}["scale_args"] == "pass"


def test_an_earlier_nodes_change_is_carried_not_reviewed(checkout, tmp_path):
    # the reader node's converter change sits uncommitted in the same checkout
    (checkout / "conversion").mkdir()
    (checkout / "conversion/muse_spark.py").write_text("# converter change of the earlier node\n", encoding="utf-8",
                                                      newline="\n")
    carried = tmp_path / "reader.diff"
    carried.write_bytes(subprocess.run(["git", "-C", str(checkout), "diff", "--no-index", "--", "/dev/null",
                                        "conversion/muse_spark.py"], capture_output=True).stdout)
    files = patchlib.parse_patch((FIXTURES / "good.diff").read_text(encoding="utf-8"))
    post = patchlib.post_images(files, lambda p: (STOCK / p).read_text(encoding="utf-8"))
    (checkout / MODEL).write_text(post[MODEL], encoding="utf-8", newline="\n")
    out = call(checkout=str(checkout), build=False, require_stage=STATIC)
    assert not out["done"] and "allowed_paths" in failed(out)
    out = call(checkout=str(checkout), build=False, require_stage=STATIC, carried_diff=str(carried))
    assert out["done"], out["checks"]


# ---- tiny pack inputs -------------------------------------------------------------------------------------
GGML = {"f32": (0, 1, 4), "nvfp4": (40, 64, 36)}


def write_gguf(path, tensors):
    """Minimal GGUF v3: tensors [(name, shape, type)], zero data."""
    def string(x):
        return struct.pack("<Q", len(x.encode())) + x.encode()
    meta = {"general.architecture": "muse-spark", "general.alignment": 32}
    head = b"GGUF" + struct.pack("<IQQ", 3, len(tensors), len(meta))
    head += string("general.architecture") + struct.pack("<I", 8) + string("muse-spark")
    head += string("general.alignment") + struct.pack("<II", 4, 32)
    blobs, offset = [], 0
    for name, shape, type_ in tensors:
        tid, block, size = GGML[type_]
        n = 1
        for d in shape:
            n *= d
        nbytes = n // block * size
        head += string(name) + struct.pack("<I", len(shape)) + b"".join(struct.pack("<Q", d) for d in shape)
        head += struct.pack("<IQ", tid, offset)
        pad = (-nbytes) % 32
        blobs.append(bytes(nbytes + pad))
        offset += nbytes + pad
    head += bytes((-len(head)) % 32)
    Path(path).write_bytes(head + b"".join(blobs))


@pytest.fixture
def tiny(tmp_path):
    d = tmp_path / "tiny"
    d.mkdir()
    write_gguf(d / "tiny-bf16.gguf", [("blk.1.ffn_up_exps.weight", [64, 8, 4], "f32")])
    write_gguf(d / "tiny-nvfp4-f32.gguf", [("blk.1.ffn_up_exps.weight", [64, 8, 4], "nvfp4"),
                                           ("blk.1.ffn_up_exps.scale", [4], "f32")])
    write_gguf(d / "tiny-deqref-f32.gguf", [("blk.1.ffn_up_exps.weight", [64, 8, 4], "f32"),
                                            ("blk.1.attn_q.weight", [64, 8], "f32")])
    return d


def digests(d):
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(Path(d).glob("*.gguf"))}


def test_tiny_packs_pinned_by_digest(checkout, tiny, tmp_path):
    manifest = tmp_path / "tiny-packs.sha256.json"
    manifest.write_text(json.dumps({"format": "factory.tiny-packs/1", "files": digests(tiny)}))
    base = dict(checkout=str(checkout), diff_path=str(FIXTURES / "good.diff"), build=False, require_stage=STATIC,
                tiny_dir=str(tiny))
    out = call(**base, tiny_packs_manifest=str(manifest))
    st = {c["name"]: c["status"] for c in out["checks"]}
    assert out["done"] and st["tiny_packs_pinned"] == "pass" and st["tiny_packs_distinct"] == "pass", out["checks"]
    pinned = digests(tiny)
    pinned["tiny-nvfp4-f32.gguf"] = "0" * 64
    manifest.write_text(json.dumps({"files": [{"name": k, "sha256": v} for k, v in pinned.items()]}))
    out = call(**base, tiny_packs_manifest=str(manifest))
    assert not out["done"] and "tiny_packs_pinned" in failed(out)


def test_reference_pack_must_not_be_the_nvfp4_pack(checkout, tiny):
    base = dict(checkout=str(checkout), diff_path=str(FIXTURES / "good.diff"), build=False, require_stage=STATIC,
                tiny_dir=str(tiny))
    out = call(**base, ref_pack="tiny-nvfp4-f32.gguf")
    assert not out["done"] and {"tiny_packs_distinct", "reference_pack_dequantized"} <= failed(out)
    shutil.copyfile(tiny / "tiny-nvfp4-f32.gguf", tiny / "copy.gguf")  # same bytes under another name
    out = call(**base, ref_pack="copy.gguf")
    assert "tiny_packs_distinct" in failed(out)
    st = {c["name"]: c["status"] for c in out["checks"]}
    assert st["compile"] == "skipped" and st["runtime_acceptance"] == "skipped"


# ---- runtime parsers ---------------------------------------------------------------------------------------
def test_kld_parse():
    text = ("Mean PPL(Q)                   : 208459.219456 ± 1.0\nMean PPL(base)                : 208363.475588 ± 1\n"
            "Mean    KLD:   0.001314 ±   0.000105\nSame top p: 59.722 ± 1.4 %\n")
    got = kld_compare.parse(text)
    assert got == {"mean_kld": 0.001314, "ppl_q": 208459.219456, "ppl_base": 208363.475588, "same_top_p": 59.722}
    assert not kld_compare.finite([kld_compare.parse("Mean    KLD:        nan ±   0.0\n")["mean_kld"]])


def dump(path, values):
    lines = []
    for name, vals in values.items():
        lines += [f"common_debug_cb_eval:   {name} = (f32)        MUL(a{{4, 1, 1, 1}}) = {{4, 1, 1, 1}}",
                  "    [", "        [", "            [" + ", ".join(f"{v:12.4f}" for v in vals) + "  ],",
                  "        ],", "    ]", f"    sum = {sum(vals):.6f}"]
    Path(path).write_text("\n".join(lines) + "\n")


def test_slice_compare_matches_scaled_names_and_flags_a_wrong_scale(tmp_path):
    ref = {f"{n}-1": [1.0, -2.0, 0.5, 3.0] for n in ("ffn_moe_gate", "ffn_moe_up", "ffn_moe_down", "ffn_moe_out")}
    good = {"ffn_moe_gate_scaled-1": [1.001, -2.0, 0.5, 3.0], "ffn_moe_up_scaled-1": [1.0, -2.0, 0.5, 2.99],
            "ffn_moe_down_scaled-1": [1.0, -2.0, 0.5, 3.0], "ffn_moe_out-1": [1.0, -2.0, 0.5, 3.0]}
    dump(tmp_path / "ref.log", ref)
    dump(tmp_path / "good.log", good)
    assert slice_compare.compare(tmp_path / "good.log", tmp_path / "ref.log", 1)["ok"]
    bad = dict(good, **{"ffn_moe_up_scaled-1": [3.0, -6.0, 1.5, 9.0]})
    dump(tmp_path / "bad.log", bad)
    res = slice_compare.compare(tmp_path / "bad.log", tmp_path / "ref.log", 1)
    assert not res["ok"] and res["worst_rel_err"] > 1.0
    missing = {k: v for k, v in good.items() if not k.startswith("ffn_moe_down")}
    dump(tmp_path / "missing.log", missing)
    assert not slice_compare.compare(tmp_path / "missing.log", tmp_path / "ref.log", 1)["ok"]


# ---- full build and runtime on the spike host --------------------------------------------------------------
TREE, TINY = os.environ.get("MUSE_SPIKE_TREE"), os.environ.get("MUSE_TINY_DIR")


@pytest.mark.skipif(not (TREE and TINY), reason="set MUSE_SPIKE_TREE and MUSE_TINY_DIR on the Spark")
@pytest.mark.parametrize("diff,bad", [("good.diff", set()), ("up-gets-gate-scale.diff", {"scale_args", "expert_slice"})])
def test_runtime_acceptance_on_tiny_packs(tmp_path, diff, bad):
    inputs = dict(checkout=TREE, diff_path=str(FIXTURES / diff), tiny_dir=TINY, work_dir=str(tmp_path), jobs=8,
                  runtime_even_if_static_fails=True)
    if os.environ.get("MUSE_STOCK_BIN"):
        inputs["stock_bin"] = os.environ["MUSE_STOCK_BIN"]
    out = call(**inputs)
    st = {c["name"]: c["status"] for c in out["checks"]}
    assert st["compile"] == "pass"
    if not bad:
        assert out["done"] and all(st[n] == "pass" for n in ("scale_free_parity", "nvfp4_kld", "no_nan", "expert_slice"))
    else:
        assert bad <= failed(out)
