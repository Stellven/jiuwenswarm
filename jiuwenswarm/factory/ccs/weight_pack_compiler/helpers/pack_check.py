"""Verifier for a written pack: shards, census against the recipe or source, carried `.scale` bytes, size.

Fails closed: an unreadable shard or header, or a missing reference, is a failing check, never a skip.
Also builds the pack manifest (`factory.pack-manifest/1`); per-file sha256 only with hash=True.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gguf_pack import census, load_pack, pack_digest, read_tensor, role_of  # noqa: E402

STAGE = "native CC execution"
MANIFEST = "factory.pack-manifest/1"


def manifest_of(pack):
    files = [{k: f[k] for k in ("name", "bytes", "mtime", "header_sha256", "sha256") if k in f} for f in pack["files"]]
    return {"format": MANIFEST, "files": files, "digest": pack_digest(pack["files"]),
            "hashed": all("sha256" in f for f in files), "tensors": len(pack["tensors"]),
            "total_bytes": sum(f["bytes"] for f in files), "census": census(pack["tensors"]),
            "architecture": pack["metadata"].get("general.architecture"),
            "file_type": pack["metadata"].get("general.file_type"),
            "imatrix_file": pack["metadata"].get("quantize.imatrix.file")}


def carried(name):
    """Tensors the requantization must carry byte for byte: per-expert scales and every input scale."""
    return role_of(name) == "expert_scale" or name.endswith(".input_scale")


def verify_pack(pack_path, recipe=None, source_pack=None, expect_bytes_range=None, target=None, hash_files=False):
    checks = []

    def add(name, ok, detail, status=None):
        checks.append({"name": name, "status": status or ("pass" if ok else "fail"), "stage": STAGE,
                       "detail": detail})

    try:
        pack = load_pack(pack_path, hash_files=hash_files)
    except (OSError, ValueError) as exc:
        add("pack_readable", False, f"{pack_path}: {exc}")
        return checks, None
    out = pack["tensors"]
    add("pack_readable", True, f"{len(pack['files'])} shard(s), {len(out)} tensors, headers read")

    source = None
    if source_pack:
        try:
            source = load_pack(source_pack)
        except (OSError, ValueError) as exc:
            add("source_readable", False, f"{source_pack}: {exc}")
    target = (target or (recipe or {}).get("target") or "q2_k").lower()
    if recipe is not None:
        reference = {t["name"]: (t["target_type"], t["shape"]) for t in recipe.get("tensors", [])}
        basis = "recipe"
    elif source is not None:
        reference = {n: (target if role_of(n) == "routed_expert" else r["type"], r["shape"]) for n, r in source["tensors"].items()}
        basis = "source"
    else:
        reference, basis = None, None

    routed = [r for r in out.values() if role_of(r["name"]) == "routed_expert"]
    wrong = [f"{r['name']}={r['type']}" for r in routed if r["type"] != target]
    add("expert_types", bool(routed) and not wrong,
        f"{len(routed)} routed expert weights are {target}" if routed and not wrong
        else ("no routed expert weights found" if not routed else f"not {target}: {wrong[:10]}"))

    if reference is None:
        add("non_expert_types", False, "no recipe or source_pack to compare against (fails closed)")
        add("tensor_set", False, "no recipe or source_pack to compare against (fails closed)")
    else:
        moved = [f"{n}: {r['type']} (expected {reference[n][0]})" for n, r in out.items()
                 if n in reference and role_of(n) != "routed_expert" and r["type"] != reference[n][0]]
        add("non_expert_types", not moved, "; ".join(moved[:10]) or f"every non-expert tensor matches the {basis}")
        lost, extra = sorted(set(reference) - set(out)), sorted(set(out) - set(reference))
        reshaped = [n for n, r in out.items() if n in reference and list(r["shape"]) != list(reference[n][1])]
        add("tensor_set", not lost and not extra and not reshaped,
            "; ".join(x for x in (f"missing {lost[:10]}" if lost else "", f"extra {extra[:10]}" if extra else "",
                                  f"reshaped {reshaped[:10]}" if reshaped else "") if x)
            or f"same {len(out)} tensor names and shapes as the {basis}")

    if source is not None:
        scales = [n for n in source["tensors"] if carried(n)]
        absent = [n for n in scales if n not in out]
        add("scale_tensors_present", not absent, f"dropped: {absent[:10]}" if absent
            else f"all {len(scales)} expert .scale / .input_scale tensors present")
        changed = []
        for n in scales:
            if n in out:
                try:
                    a, b = read_tensor(source["tensors"][n]), read_tensor(out[n])
                    if a != b or source["tensors"][n]["type"] != out[n]["type"]:
                        changed.append(n)
                except (OSError, ValueError) as exc:
                    changed.append(f"{n} ({exc})")
        add("scale_tensors_identical", not changed and not absent, f"bytes differ: {changed[:10]}" if changed
            else (f"{len(scales) - len(absent)} present scale tensors byte-identical" if not absent
                  else "cannot pass while scale tensors are missing"))
        if recipe is not None:
            names = {f["name"]: f.get("header_sha256") for f in recipe.get("source", {}).get("files", [])}
            same = all(names.get(f["name"]) == f["header_sha256"] for f in source["files"]) and len(names) == len(source["files"])
            add("source_is_recipe_source", same, "source_pack headers match the recipe's source"
                if same else "source_pack is not the pack the recipe was planned from")
    else:
        add("scale_tensors_present", False, "source_pack not given: carried scales cannot be compared (fails closed)")
        add("scale_tensors_identical", False, "source_pack not given (fails closed)")

    total = sum(f["bytes"] for f in pack["files"])
    if expect_bytes_range:
        lo, hi = (int(x) for x in expect_bytes_range)
        add("total_bytes", lo <= total <= hi, f"{total} bytes, expected [{lo}, {hi}]")
    else:
        add("total_bytes", True, f"{total} bytes (no range given)", "info")
    if recipe is not None:
        est = recipe.get("estimate", {})
        want, tol = int(est.get("output_bytes", 0)), int(est.get("output_bytes_tolerance", 0)) + 4096 * len(pack["files"])
        add("recipe_size", abs(total - want) <= tol, f"{total} bytes vs recipe estimate {want} (tolerance {tol})")
        planned = recipe.get("output", {})
        if planned.get("keep_split"):
            n = len(planned.get("files", []))
            add("shard_layout", len(pack["files"]) == n, f"{len(pack['files'])} shards, recipe {n}")
        if recipe.get("imatrix"):
            got = pack["metadata"].get("quantize.imatrix.file")
            add("imatrix_recorded", got == Path(recipe["imatrix"]["path"]).name,
                f"quantize.imatrix.file={got!r}, recipe {Path(recipe['imatrix']['path']).name!r}")
    return checks, manifest_of(pack)


def load_recipe(path):
    return json.loads(Path(path).read_text(encoding="utf-8")) if path else None
