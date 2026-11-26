"""Tiny synthetic GGUF v3 packs for the weight pack compiler tests (standard library only).

`make_source` writes a two-shard NVFP4 Muse-like pack; `make_q2` writes what stock llama-quantize would
produce from it with the Q2 recipe (routed experts Q2_K, everything else carried). Faults are planted by
keyword so each test names exactly what it breaks.
"""
import struct
from pathlib import Path

TYPES = {"f32": (0, 1, 4), "q8_0": (8, 32, 34), "q2_k": (10, 256, 84), "q4_k": (12, 256, 144),
         "bf16": (30, 1, 2), "nvfp4": (40, 64, 36), "iq1_s": (19, 256, 50), "iq2_xxs": (16, 256, 66)}
N_EXPERT, N_EMBD, N_FF, N_LAYER = 4, 256, 256, 3


def nbytes(type_, shape):
    _, block, size = TYPES[type_]
    n = 1
    for d in shape:
        n *= d
    assert shape[0] % block == 0, (type_, shape)
    return n // block * size


def _str(s):
    b = s.encode()
    return struct.pack("<Q", len(b)) + b


def _kv(key, value):
    out = _str(key)
    if isinstance(value, bool):
        return out + struct.pack("<I?", 7, value)
    if isinstance(value, int):
        return out + struct.pack("<IQ", 10, value) if value > 0xFFFFFFFF else out + struct.pack("<II", 4, value)
    if isinstance(value, float):
        return out + struct.pack("<If", 6, value)
    if isinstance(value, str):
        return out + struct.pack("<I", 8) + _str(value)
    raise TypeError(value)


def write_gguf(path, tensors, metadata, alignment=32):
    """tensors: list of (name, shape, type, data or None for zeros)."""
    head = b"GGUF" + struct.pack("<IQQ", 3, len(tensors), len(metadata))
    head += b"".join(_kv(k, v) for k, v in metadata.items())
    blobs, offset = [], 0
    for name, shape, type_, data in tensors:
        size = nbytes(type_, shape)
        data = bytes(size) if data is None else data
        assert len(data) == size, (name, len(data), size)
        head += _str(name) + struct.pack("<I", len(shape)) + b"".join(struct.pack("<Q", d) for d in shape)
        head += struct.pack("<IQ", TYPES[type_][0], offset)
        pad = (-size) % alignment
        blobs.append(data + bytes(pad))
        offset += size + pad
    head += bytes((-len(head)) % alignment)
    Path(path).write_bytes(head + b"".join(blobs))


def floats(*values):
    return struct.pack(f"<{len(values)}f", *values)


def layout(expert_type="nvfp4", overrides=None, drop=(), scale_shift=0.0, n_embd=N_EMBD):
    """[(shard, name, shape, type, data)] for the Muse-like pack."""
    overrides = overrides or {}
    rows = [(0, "token_embd.weight", [n_embd, 8], "q4_k" if n_embd % 256 == 0 else "q8_0", None),
            (0, "output_norm.weight", [n_embd], "f32", floats(*([1.0] * n_embd))),
            (0, "output.weight", [n_embd, 8], "q8_0", None)]
    for layer in range(N_LAYER):
        shard = 0 if layer == 0 else 1
        p = f"blk.{layer}."
        rows += [(shard, p + "attn_norm.weight", [n_embd], "f32", None),
                 (shard, p + "attn_q.weight", [n_embd, 64], "q8_0", None),
                 (shard, p + "attn_q.input_scale", [1], "f32", floats(0.5 + layer)),
                 (shard, p + "ffn_gate_inp.weight", [n_embd, N_EXPERT], "f32", None),
                 (shard, p + "ffn_gate_shexp.weight", [n_embd, 64], "nvfp4", None)]
        for part, shape in (("gate", [n_embd, N_FF, N_EXPERT]), ("up", [n_embd, N_FF, N_EXPERT]),
                            ("down", [N_FF, n_embd, N_EXPERT])):
            rows.append((shard, p + f"ffn_{part}_exps.weight", shape, expert_type, None))
            rows.append((shard, p + f"ffn_{part}_exps.scale", [N_EXPERT], "f32",
                         floats(*[layer + 0.25 * e + scale_shift for e in range(N_EXPERT)])))
        rows.append((shard, p + "ffn_gate_exps.input_scale", [N_EXPERT], "f32", floats(1.0, 2.0, 3.0, 4.0)))
    out = []
    for shard, name, shape, type_, data in rows:
        if name in drop:
            continue
        if overrides.get(name, type_) != type_:
            type_, data = overrides[name], None
        out.append((shard, name, shape, type_, data))
    return out


def write_pack(prefix, rows, extra_meta=None, shards=2):
    paths = []
    for shard in range(shards):
        meta = {"general.architecture": "muse-spark", "general.alignment": 32, "split.no": shard,
                "split.count": shards, "split.tensors.count": len(rows), **(extra_meta or {})}
        path = Path(f"{prefix}-{shard + 1:05d}-of-{shards:05d}.gguf")
        write_gguf(path, [(n, s, t, d) for sh, n, s, t, d in rows if sh == shard], meta)
        paths.append(path)
    return paths


def make_source(directory, **kw):
    return write_pack(Path(directory) / "muse-nvfp4", layout(**kw))


def make_q2(directory, name="muse-nvfp4-Q2_K", imatrix_name="imatrix.gguf", expert_type="q2_k", **kw):
    meta = {"general.file_type": 10, **({"quantize.imatrix.file": imatrix_name} if imatrix_name else {})}
    return write_pack(Path(directory) / name, layout(expert_type=expert_type, **kw), meta)
