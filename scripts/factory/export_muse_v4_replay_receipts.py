"""Export the two Muse V4 production receipts into a new, host-controlled directory.

The V4 database is opened immutable. Large GGUF files are read only for headers
and tensor directories. The manifest SHA-256 is derived from historical records
before comparison with the manifest currently beside the pack.

From the integrated worktree:
    python3 -m scripts.factory.export_muse_v4_replay_receipts \
        --source-home ~/muse-demo/graph-v4 --output-dir ~/muse-demo/replay-r8
"""

import argparse
from collections import Counter
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
import re
import sqlite3
import sys
from pathlib import Path

HELPERS = (Path(__file__).resolve().parents[2] / "jiuwenswarm" / "factory" /
           "ccs" / "weight_pack_compiler" / "helpers")
sys.path.insert(0, str(HELPERS))
from gguf_pack import census, load_pack, pack_digest  # noqa: E402


SOURCE_RUN = "muse-2bit-ttft-v4"
CONVERT = "1a040f7126cb485581b3b317932290f4"
QUANTIZE = "b117d0f1e0e3428ebba1b7c681277d8b"
BUILD = "41dde95d9b4a4758957e1773c34a28b2"
PINS = "39471b3a95144c1bb25627783bd126f7"
NVFP4_VERIFICATION = "96a32aab7c86458fa0c5edb2025fba8d"
QUANTIZE_VERIFICATION = "57bbcb1be98f4f3282d4f70470d4d5df"
SHA256 = re.compile(r"[0-9a-f]{64}")
COMMIT = re.compile(r"[0-9a-f]{40}")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def source_file(path, root):
    path = Path(path).resolve(strict=True)
    require(path.is_relative_to(root) and path.is_file(), f"source file outside {root}: {path}")
    return path


def artifact(db, home, artifact_id):
    row = db.execute(
        "SELECT location, sha256, size, complete FROM artifacts WHERE task_id=? AND artifact_id=?",
        (SOURCE_RUN, artifact_id),
    ).fetchone()
    require(row is not None and row["complete"], f"missing complete artifact {artifact_id}")
    path = source_file(home / row["location"], home / "artifacts")
    require(path.stat().st_size == row["size"] <= 4 << 20, f"unexpected artifact size for {artifact_id}")
    data = path.read_bytes()
    require(sha256(data) == row["sha256"], f"artifact checksum mismatch for {artifact_id}")
    return json.loads(data), row["sha256"]


def observation(db, obs_id, kind):
    row = db.execute(
        'SELECT * FROM observations WHERE task_id=? AND obs_id=? AND kind=?',
        (SOURCE_RUN, obs_id, kind),
    ).fetchone()
    require(row is not None, f"missing {kind} observation {obs_id}")
    return json.loads(row["values"]), row


def job(db, home, attempt_id, recipe, node):
    row = db.execute(
        "SELECT * FROM attempts WHERE task_id=? AND attempt_id=?", (SOURCE_RUN, attempt_id)
    ).fetchone()
    require(row is not None and row["state"] == "succeeded" and row["jobq_id"]
            and 0 < row["started"] <= row["ended"], f"missing successful {recipe} job {attempt_id}")
    records = db.execute(
        """SELECT * FROM observations WHERE task_id=? AND kind='capped_run'
           AND json_extract(host_run, '$.attempt_id')=?""",
        (SOURCE_RUN, attempt_id),
    ).fetchall()
    require(len(records) == 1, f"expected one capped-run observation for {attempt_id}")
    record = records[0]
    artifact_id = f"run-{attempt_id[:12]}-result.json"
    require(artifact_id in json.loads(record["source_artifacts"]), f"missing result link for {attempt_id}")
    doc, digest = artifact(db, home, artifact_id)
    require(doc == json.loads(record["values"]) and doc["format"] == "factory.capped-run/1"
            and doc["outcome"] == "ok" and doc["recipe"] == recipe and doc["node_id"] == node
            and doc["attempt_id"] == attempt_id and doc["request"] == json.loads(row["request"])
            and doc["request"]["recipe"] == recipe and doc["request"]["node_id"] == node
            and doc["seconds"] > 0, f"inconsistent capped-run result for {attempt_id}")
    return doc, row, record, digest


def checkpoint_pins(db, home, convert, start):
    pins, record = observation(db, PINS, "pins")
    checkpoint = pins["checkpoint"]
    operator, operator_record = observation(db, checkpoint["operator_input_id"], "operator_input")
    artifact_id = operator["artifact_id"]
    require(operator["key"] == "checkpoint_digests"
            and artifact_id in json.loads(operator_record["source_artifacts"])
            and artifact_id in json.loads(record["source_artifacts"])
            and operator_record["created"] <= record["created"] <= start,
            "checkpoint pins were not attached before conversion")
    doc, digest = artifact(db, home, artifact_id)
    historical = doc["checkpoint"]
    require(doc["format"] == "muse-pins/1" and operator["sha256"] == digest
            and checkpoint["operator_manifest_sha256"] == digest
            and historical["root"] == checkpoint["root"] == convert["request"]["checkpoint"]
            and all(historical[key] == checkpoint[key] for key in ("repo_commit", "small_files_sha256"))
            and doc["imatrix"] == pins["imatrix"],
            "checkpoint pins, operator artifact and conversion request disagree")
    require(historical["shards"] and checkpoint["shards"] == {
        name: row["sha256"] for name, row in historical["shards"].items()
    } and len(historical["shards"]) == checkpoint["shard_count"]
            and sum(row["bytes"] for row in historical["shards"].values()) == checkpoint["shard_bytes"]
            and all(SHA256.fullmatch(digest) for digest in checkpoint["shards"].values()),
            "checkpoint shard digest inventory is inconsistent")
    return doc, digest


def normalized_rows(rows, keys):
    return [{key: row[key] for key in keys} for row in rows]


def verified_pack(home, first, manifest, manifest_job, historical):
    packs = home / "packs"
    first = source_file(first, packs)
    manifest = source_file(manifest, first.parent)
    recorded = manifest_job["result"]
    require(recorded["manifest"] == str(manifest)
            and (recorded.get("first_shard") or recorded["pack"]) == str(first),
            f"manifest job does not identify {first.name}")
    hashed_keys = ("name", "bytes", "sha256")
    rows = normalized_rows(recorded["files"], hashed_keys)
    require(rows and all(SHA256.fullmatch(row["sha256"]) for row in rows)
            and rows == normalized_rows(historical["files"], hashed_keys),
            f"recorded shard digests disagree for {first.name}")
    total = sum(row["bytes"] for row in rows)
    require(total == recorded["bytes"] == historical["total_bytes"], f"pack bytes disagree for {first.name}")
    # The V4 runner deterministically rendered the sidecar from these recorded rows.
    expected = dict(format="factory.pack-manifest/1", files=rows, bytes=total,
                    written_by="factory.capped_runner (host sha256)", attempt_id=manifest_job["attempt_id"])
    expected_bytes = json.dumps(expected, indent=1).encode("utf-8")
    require(manifest.stat().st_size == len(expected_bytes) and manifest.read_bytes() == expected_bytes,
            f"pack manifest differs from historical records: {manifest}")
    for row in rows:
        require(Path(row["name"]).name == row["name"], f"invalid shard name {row['name']}")
        source_file(first.parent / row["name"], first.parent)
    pack = load_pack(first, hash_files=False)
    header_keys = ("name", "bytes", "header_sha256")
    role_census = census(pack["tensors"])
    require(normalized_rows(pack["files"], header_keys) == normalized_rows(historical["files"], header_keys)
            and role_census == historical["census"]
            and pack["metadata"]["general.architecture"] == historical["architecture"],
            f"live GGUF header census differs from historical records: {first.name}")
    files = [dict(row, header_sha256=header["header_sha256"])
             for row, header in zip(rows, pack["files"], strict=True)]
    return dict(pack_dir=str(first.parent), first_shard=first.name, manifest=manifest.name,
                manifest_sha256=sha256(expected_bytes), bytes=total, files=files,
                header_digest=pack_digest(pack["files"]), tensors=len(pack["tensors"]),
                census=role_census, census_by_type=dict(Counter(t["type"] for t in pack["tensors"].values())))


def receipt(production, inputs, output, **proof):
    doc, attempt, record, digest = production
    return dict(
        recipe=doc["recipe"],
        inputs=inputs,
        output=output,
        run_id=SOURCE_RUN,
        recorded_at=datetime.fromtimestamp(attempt["ended"], timezone.utc).isoformat(timespec="seconds"),
        duration_seconds=doc["seconds"],
        provenance=dict(
            attempt_id=doc["attempt_id"],
            queue_job_id=attempt["jobq_id"],
            outcome_observation=record["obs_id"],
            result_artifact_sha256=digest,
            **proof,
        ),
    )


def export_records(db, home):
    conversion = job(db, home, CONVERT, "convert", "ingest_nvfp4")
    quantization = job(db, home, QUANTIZE, "quantize", "requant_2bit")
    convert, convert_attempt, convert_obs, _ = conversion
    quant, quant_attempt, quant_obs, _ = quantization
    pins, checkpoint_digest = checkpoint_pins(db, home, convert, convert_attempt["started"])

    nvfp4, nvfp4_obs = observation(db, NVFP4_VERIFICATION, "nvfp4_pack_manifest")
    native, _ = observation(db, QUANTIZE_VERIFICATION, "mixed_2bit_pack_native_verification")
    projection, _ = observation(db, native["recipe_projection_id"], "mixed_2bit_probe_timing_projection")
    verified_id = projection["verified_recipe_id"]
    verified, verified_obs = observation(db, verified_id, "verified_mixed_2bit_recipe")
    require(nvfp4["attempt_id"] == CONVERT and nvfp4["capped_run_id"] == convert_obs["obs_id"]
            and nvfp4["verifier"]["done"] and all(check["status"] == "pass" for check in nvfp4["verifier"]["checks"]),
            "NVFP4 verification does not identify the original successful conversion")
    require(native["attempt_id"] == QUANTIZE and native["capped_run_id"] == quant_obs["obs_id"]
            and native["verifier_done"] and native["host_shards_match_verified_names_and_sizes"]
            and native["first_shard"] == quant["result"]["first_shard"]
            and native["manifest_path"] == quant["result"]["manifest"]
            and native["wall_seconds"] == quant["seconds"] and not quant["request"]["probe"],
            "2-bit verification does not identify the original full quantization")
    require(nvfp4_obs["created"] <= verified_obs["created"] <= quant_attempt["started"]
            and verified["verifier_done"] and verified["accepted_manifest_id"] == NVFP4_VERIFICATION
            and verified["source_shard_hashes_match"] and verified["imatrix_sha256_matches_pinned"],
            "verified quantization recipe does not use the accepted NVFP4 pack")

    historical_hash_job = job(db, home, nvfp4["hash_attempt_id"], "manifest", "ingest_nvfp4")
    require(historical_hash_job[2]["obs_id"] == nvfp4["hash_capped_run_id"]
            and historical_hash_job[0]["request"]["pack"] == convert["result"]["first_shard"]
            and historical_hash_job[0]["result"]["files"] == normalized_rows(
                nvfp4["manifest"]["files"], ("name", "bytes", "sha256")
            ), "original NVFP4 hash job does not match accepted verification")
    regenerated, _ = observation(db, verified["manifest_run_id"], "capped_run")
    manifest_job = job(db, home, regenerated["attempt_id"], "manifest", "requant_2bit")
    require(manifest_job[2]["obs_id"] == verified["manifest_run_id"]
            and manifest_job[1]["ended"] <= verified_obs["created"],
            "regenerated NVFP4 manifest job does not match the verified recipe")
    first = convert["result"]["first_shard"]
    nvfp4_pack = verified_pack(home, first, verified["pack_manifest"], manifest_job[0], nvfp4["manifest"])
    two_bit_pack = verified_pack(home, native["first_shard"], native["manifest_path"], quant,
                                 native["hashed_shard_manifest"])
    require(convert["result"]["files"] == normalized_rows(nvfp4_pack["files"], ("bytes", "name"))
            and convert["result"]["bytes"] == nvfp4_pack["bytes"],
            "original conversion shard names and sizes do not match the manifest")
    require(two_bit_pack["header_digest"] == native["live_header_manifest_digest"],
            "2-bit header digest does not match historical verification")

    convert_request = convert["request"]
    converter = convert_request["commit"]
    converter_marker = home / "snapshots" / converter[:12] / ".factory-commit"
    require(COMMIT.fullmatch(converter) and converter == convert["result"]["commit"]
            and source_file(converter_marker, home / "snapshots").read_text().strip() == converter,
            "conversion commit does not match the historical snapshot")
    quant_request = quant["request"]
    build, build_job, _, build_artifact_digest = job(db, home, BUILD, "build", "build_base_engine")
    quantizer = build["result"]["commit"]
    binary = build["result"]["binaries"]["llama-quantize"]
    build_marker = home / "builds" / build["request"]["name"] / "src" / ".factory-commit"
    require(COMMIT.fullmatch(quantizer) and quantizer == build["request"]["commit"]
            and source_file(build_marker, home / "builds").read_text().strip() == quantizer
            and build_job["ended"] <= quant_attempt["started"]
            and binary["path"] == quant_request["argv"][0] and SHA256.fullmatch(binary["sha256"]),
            "quantizer does not match the recorded build")

    require(verified["recipe"] == projection["recipe"] == quant_request["recipe_path"] == quant["result"]["recipe"],
            "production quantization does not reference the verified recipe")
    recipe_path = source_file(verified["recipe"], home / "agent-workspace" / "work")
    require(recipe_path.stat().st_size <= 4 << 20, "unexpected quantization recipe size")
    recipe = json.loads(recipe_path.read_bytes())
    source = recipe["source"]
    imatrix = recipe["imatrix"]
    source_keys = ("name", "bytes", "sha256", "header_sha256")
    require(recipe["format"] == "factory.pack-recipe/1"
            and recipe["argv"] == quant_request["argv"] == quant["result"]["argv"]
            and source["files"][0]["path"] == first
            and normalized_rows(source["files"], source_keys) == normalized_rows(nvfp4_pack["files"], source_keys)
            and source["digest"] == pack_digest(nvfp4_pack["files"]) == verified["source_digest"]
            and imatrix == verified["imatrix"]
            and all(imatrix[key] == pins["imatrix"][key] for key in ("path", "sha256"))
            and SHA256.fullmatch(imatrix["sha256"])
            and recipe["target"] == verified["target"]
            and recipe["output"]["path"] == quant_request["output"],
            "quantization recipe arguments, source, imatrix or target disagree with historical evidence")

    convert_inputs = dict(producer_commit=converter, checkpoint_manifest_sha256=checkpoint_digest,
                          outtype=convert_request["outtype"], split_max_size=convert_request["split_max_size"])
    from jiuwenswarm.factory.capped_replay import quantize_argv_digest

    quant_inputs = dict(producer_commit=quantizer, source_digest=source["digest"], imatrix_sha256=imatrix["sha256"],
                        target=recipe["target"], argv_sha256=quantize_argv_digest(quant_request["argv"]))
    return {
        CONVERT: receipt(conversion, convert_inputs, nvfp4_pack, checkpoint_pins_observation=PINS,
                         verification_observation=NVFP4_VERIFICATION, manifest_attempt=regenerated["attempt_id"],
                         manifest_result_artifact_sha256=manifest_job[3]),
        QUANTIZE: receipt(quantization, quant_inputs, two_bit_pack, recipe_observation=verified_id,
                          verification_observation=QUANTIZE_VERIFICATION, quantizer_build_attempt=BUILD,
                          quantizer_build_result_artifact_sha256=build_artifact_digest,
                          quantizer_binary_sha256=binary["sha256"]),
    }


def export(source_home, output_dir):
    source_home = source_home.expanduser().resolve(strict=True)
    output_dir = output_dir.expanduser()
    require(not output_dir.is_symlink(), f"receipt directory cannot be a symlink: {output_dir}")
    output_dir = output_dir.resolve()
    require(not output_dir.is_relative_to(source_home), "receipt directory must be outside the source graph")
    require(not output_dir.exists(), f"receipt directory already exists: {output_dir}")
    db_path = source_file(source_home / "factory.sqlite", source_home)
    wal = db_path.with_name(f"{db_path.name}-wal")
    require(not wal.exists() or wal.stat().st_size == 0, "source SQLite has uncheckpointed WAL data")
    with closing(sqlite3.connect(f"{db_path.as_uri()}?mode=ro&immutable=1", uri=True)) as db:
        db.row_factory = sqlite3.Row
        receipts = export_records(db, source_home)
    registry = {"schema": "factory.capped-replay-registry/1", "receipts": receipts}
    output_dir.mkdir(mode=0o700)
    # Publish the registry last so it is never visible before its individual evidence files.
    for name, data in (("convert", receipts[CONVERT]), ("quantize", receipts[QUANTIZE]), ("registry", registry)):
        tmp = output_dir / f"{name}.tmp"
        tmp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        tmp.rename(output_dir / f"{name}.json")
    return output_dir / "registry.json"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-home", type=Path, required=True, help="Historical V4 factory home")
    parser.add_argument("--output-dir", type=Path, required=True, help="New directory outside the V4 graph")
    args = parser.parse_args()
    try:
        registry = export(args.source_home, args.output_dir)
    except (ImportError, OSError, ValueError, KeyError, TypeError, sqlite3.Error) as exc:
        parser.exit(1, f"Replay receipt export failed: {exc}\n")
    print(registry)


if __name__ == "__main__":
    main()
