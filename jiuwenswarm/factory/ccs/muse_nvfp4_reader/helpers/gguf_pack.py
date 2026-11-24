"""Read a GGUF pack (one file or a split set) with the standard library: header, tensor census, raw tensor bytes.

Copied from weights.build_weight_pack_compiler (helpers/gguf_pack.py) so this capsule stands alone.

Never maps or loads tensor data except when asked for one tensor's bytes (used for the small F32 `.scale` tensors).
A tensor's offset in the header is relative to the start of the data section, which begins at the first
`general.alignment` boundary after the tensor table.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import struct

MAGIC = b"GGUF"
SCALAR = {0: "<B", 1: "<b", 2: "<H", 3: "<h", 4: "<I", 5: "<i", 6: "<f", 7: "<?", 10: "<Q", 11: "<q", 12: "<d"}
# ggml type id -> (name, elements per block, bytes per block). Ids: ggml/include/ggml.h:219-263 at 9048bad8.
# Sizes: the static_asserts in ggml/src/ggml-common.h at the same pin.
GGML_TYPES = {
    0: ("f32", 1, 4), 1: ("f16", 1, 2), 2: ("q4_0", 32, 18), 3: ("q4_1", 32, 20), 6: ("q5_0", 32, 22),
    7: ("q5_1", 32, 24), 8: ("q8_0", 32, 34), 9: ("q8_1", 32, 36), 10: ("q2_k", 256, 84), 11: ("q3_k", 256, 110),
    12: ("q4_k", 256, 144), 13: ("q5_k", 256, 176), 14: ("q6_k", 256, 210), 15: ("q8_k", 256, 292),
    16: ("iq2_xxs", 256, 66), 17: ("iq2_xs", 256, 74), 18: ("iq3_xxs", 256, 98), 19: ("iq1_s", 256, 50),
    20: ("iq4_nl", 32, 18), 21: ("iq3_s", 256, 110), 22: ("iq2_s", 256, 82), 23: ("iq4_xs", 256, 136),
    24: ("i8", 1, 1), 25: ("i16", 1, 2), 26: ("i32", 1, 4), 27: ("i64", 1, 8), 28: ("f64", 1, 8),
    29: ("iq1_m", 256, 56), 30: ("bf16", 1, 2), 34: ("tq1_0", 256, 54), 35: ("tq2_0", 256, 66),
    39: ("mxfp4", 32, 17), 40: ("nvfp4", 64, 36), 41: ("q1_0", 128, 18), 42: ("q2_0", 64, 18),
    43: ("f8_e4m3", 1, 1),
}
TYPE_ID = {name: tid for tid, (name, _, _) in GGML_TYPES.items()}
SPLIT = re.compile(r"^(?P<prefix>.*)-(?P<no>\d{5})-of-(?P<count>\d{5})\.gguf$")


def type_name(name):
    """Canonical lower-case ggml type name (`Q2_K` -> `q2_k`); raises on an unknown name."""
    key = str(name).strip().lower()
    if key not in TYPE_ID:
        raise ValueError(f"unknown ggml type {name!r}")
    return key


def block_of(name):
    _, block, size = GGML_TYPES[TYPE_ID[type_name(name)]]
    return block, size


def nbytes(type_, shape):
    """Bytes of a tensor of this type and ggml shape (ne[0] first). Raises when ne[0] is not whole blocks."""
    block, size = block_of(type_)
    if not shape or shape[0] % block:
        raise ValueError(f"row length {shape[0] if shape else 0} is not a multiple of the {type_} block of {block}")
    n = 1
    for dim in shape:
        n *= dim
    return n // block * size


def padded(n, alignment):
    return (n + alignment - 1) // alignment * alignment


class _Reader:
    def __init__(self, handle):
        self.handle = handle

    def take(self, size):
        data = self.handle.read(size)
        if len(data) != size:
            raise ValueError("GGUF header is truncated")
        return data

    def unpack(self, fmt):
        return struct.unpack(fmt, self.take(struct.calcsize(fmt)))[0]

    def string(self):
        length = self.unpack("<Q")
        if length > 1 << 24:
            raise ValueError("GGUF string length is implausible")
        return self.take(length).decode("utf-8", errors="replace")

    def value(self, vtype):
        if vtype in SCALAR:
            return self.unpack(SCALAR[vtype])
        if vtype == 8:
            return self.string()
        if vtype == 9:
            etype, count = self.unpack("<I"), self.unpack("<Q")
            if count > 1 << 26:
                raise ValueError("GGUF array length is implausible")
            items = [self.value(etype) for _ in range(count)]
            return items if count <= 64 else {"array_of": etype, "count": count}
        raise ValueError(f"unknown GGUF value type {vtype}")


def read_header(path):
    """{path, version, alignment, data_start, header_sha256, metadata, tensors}. Tensors: name, shape, type, offset."""
    path = Path(path)
    with open(path, "rb", buffering=1 << 20) as handle:
        reader = _Reader(handle)
        if reader.take(4) != MAGIC:
            raise ValueError(f"{path.name}: not a GGUF file")
        version = reader.unpack("<I")
        if version not in (2, 3):
            raise ValueError(f"{path.name}: GGUF version {version} is not supported")
        n_tensors, n_kv = reader.unpack("<Q"), reader.unpack("<Q")
        metadata = {}
        for _ in range(n_kv):
            key = reader.string()
            metadata[key] = reader.value(reader.unpack("<I"))
        tensors = []
        for _ in range(n_tensors):
            name = reader.string()
            n_dims = reader.unpack("<I")
            if n_dims > 4:
                raise ValueError(f"{path.name}: tensor {name} has {n_dims} dimensions")
            shape = [reader.unpack("<Q") for _ in range(n_dims)]
            tid, offset = reader.unpack("<I"), reader.unpack("<Q")
            if tid not in GGML_TYPES:
                raise ValueError(f"{path.name}: tensor {name} has unknown ggml type id {tid}")
            tensors.append({"name": name, "shape": shape, "type": GGML_TYPES[tid][0], "type_id": tid, "offset": offset})
        end = handle.tell()
        handle.seek(0)
        header_sha = hashlib.sha256(handle.read(end)).hexdigest()
    alignment = int(metadata.get("general.alignment", 32))
    return {"path": str(path), "version": version, "alignment": alignment, "data_start": padded(end, alignment),
            "header_sha256": header_sha, "metadata": metadata, "tensors": tensors}


def shard_paths(pack):
    """All files of a pack given its first shard, any shard, a single file or a directory holding one pack."""
    pack = Path(pack)
    if pack.is_dir():
        files = sorted(pack.glob("*.gguf"))
        firsts = [p for p in files if (SPLIT.match(p.name) and SPLIT.match(p.name)["no"] == "00001")]
        if len(firsts) == 1:
            pack = firsts[0]
        elif len(files) == 1:
            return files
        else:
            raise ValueError(f"{pack}: expected one pack (one first shard or one .gguf), found {len(files)} files")
    match = SPLIT.match(pack.name)
    if not match:
        return [pack]
    count = int(match["count"])
    return [pack.with_name(f"{match['prefix']}-{i:05d}-of-{count:05d}.gguf") for i in range(1, count + 1)]


def sha256_file(path, chunk=1 << 22):
    h = hashlib.sha256()
    with open(path, "rb") as handle:
        while block := handle.read(chunk):
            h.update(block)
    return h.hexdigest()


def load_pack(pack, hash_files=False):
    """Census of every shard. Raises ValueError on a missing shard, unreadable header or out-of-file tensor."""
    paths = shard_paths(pack)
    missing = [p.name for p in paths if not p.is_file()]
    if missing:
        raise ValueError("missing shards: " + ", ".join(missing))
    files, tensors, metadata = [], {}, {}
    for index, path in enumerate(paths):
        header = read_header(path)
        size = path.stat().st_size
        split_count = header["metadata"].get("split.count")
        if split_count is not None and int(split_count) != len(paths):
            raise ValueError(f"{path.name}: split.count {split_count} but {len(paths)} shard names")
        if index == 0:
            metadata = header["metadata"]
        for t in header["tensors"]:
            if t["name"] in tensors:
                raise ValueError(f"duplicate tensor {t['name']}")
            row = dict(t, file=str(path), shard=index, start=header["data_start"] + t["offset"],
                       nbytes=nbytes(t["type"], t["shape"]))
            if row["start"] + row["nbytes"] > size:
                raise ValueError(f"{path.name}: tensor {t['name']} runs past the end of the file")
            tensors[t["name"]] = row
        record = {"path": str(path), "name": path.name, "bytes": size, "mtime": int(os.path.getmtime(path)),
                  "header_sha256": header["header_sha256"], "header_bytes": header["data_start"],
                  "tensors": len(header["tensors"])}
        if hash_files:
            record["sha256"] = sha256_file(path)
        files.append(record)
    return {"files": files, "tensors": tensors, "metadata": metadata, "alignment": int(metadata.get("general.alignment", 32))}


def read_tensor(row, limit=1 << 26):
    """Raw bytes of one tensor (meant for small tensors such as F32 `.scale`)."""
    if row["nbytes"] > limit:
        raise ValueError(f"{row['name']} is {row['nbytes']} bytes; refusing to read it whole")
    with open(row["file"], "rb") as handle:
        handle.seek(row["start"])
        data = handle.read(row["nbytes"])
    if len(data) != row["nbytes"]:
        raise ValueError(f"{row['name']}: data is truncated")
    return data


def pack_digest(files):
    """One digest over the ordered file records: sha256 when present, otherwise size + header digest."""
    rows = [{k: f.get(k) for k in ("name", "bytes", "sha256", "header_sha256")} for f in files]
    return hashlib.sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest()


# ---- tensor roles ------------------------------------------------------------------------------------------
ROUTED = re.compile(r"^blk\.\d+\.ffn_(gate|up|down|gate_up)_exps\.weight$")
ROLES = (  # first match wins; routed_expert is checked first by role_of
    ("expert_scale", re.compile(r"_(ch)?exps\.(scale|input_scale)$")),
    ("expert_other", re.compile(r"_(ch)?exps\.")),
    ("shared_expert", re.compile(r"_shexp\.")),
    ("router", re.compile(r"\.(ffn_gate_inp|exp_probs_b)")),
    ("norm", re.compile(r"norm")),
    ("attention", re.compile(r"\.attn_")),
    ("dense_ffn", re.compile(r"\.ffn_")),
    ("embedding", re.compile(r"^(token_embd|per_layer_token_embd)\.")),
    ("output", re.compile(r"^output\.")),
)


def role_of(name):
    if ROUTED.match(name):
        return "routed_expert"
    for role, pattern in ROLES:
        if pattern.search(name):
            return role
    return "other"


def census(tensors):
    """{role: {type: count}} for a tensor table."""
    out = {}
    for row in tensors.values():
        role = out.setdefault(role_of(row["name"]), {})
        role[row["type"]] = role.get(row["type"], 0) + 1
    return out
