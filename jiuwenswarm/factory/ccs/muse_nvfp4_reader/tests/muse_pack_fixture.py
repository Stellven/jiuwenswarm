"""Tiny synthetic Muse NVFP4 GGUF packs for verify_pack (standard library only).

Four layers, eight experts: layers 1 and 2 quantized (NVFP4 experts with [E] .scale and .input_scale),
layers 0 and 3 excluded (BF16 experts, no scales), like the checkpoint's layers 0 and 61. Faults are planted
by keyword so each test names what it breaks.
"""
import json
import struct
from pathlib import Path

TYPES = {"f32": (0, 1, 4), "q8_0": (8, 32, 34), "bf16": (30, 1, 2), "nvfp4": (40, 64, 36)}
E, EMBD, FF, LAYERS, QUANTIZED = 8, 128, 64, 4, (1, 2)


def nbytes(type_, shape):
    _, block, size = TYPES[type_]
    n = 1
    for d in shape:
        n *= d
    return n // block * size


def _str(s):
    b = s.encode()
    return struct.pack("<Q", len(b)) + b


def _kv(key, value):
    out = _str(key)
    if isinstance(value, int):
        return out + struct.pack("<II", 4, value)
    if isinstance(value, str):
        return out + struct.pack("<I", 8) + _str(value)
    raise TypeError(value)


def write_gguf(path, tensors, metadata, alignment=32):
    head = b"GGUF" + struct.pack("<IQQ", 3, len(tensors), len(metadata))
    head += b"".join(_kv(k, v) for k, v in metadata.items())
    blobs, offset = [], 0
    for name, shape, type_, data in tensors:
        size = nbytes(type_, shape)
        data = bytes(size) if data is None else data
        head += _str(name) + struct.pack("<I", len(shape)) + b"".join(struct.pack("<Q", d) for d in shape)
        head += struct.pack("<IQ", TYPES[type_][0], offset)
        pad = (-size) % alignment
        blobs.append(data + bytes(pad))
        offset += size + pad
    head += bytes((-len(head)) % alignment)
    Path(path).write_bytes(head + b"".join(blobs))


def floats(*values):
    return struct.pack(f"<{len(values)}f", *values)


def rows(overrides=None, drop=(), bad_scale=None):
    overrides = overrides or {}
    out = [("token_embd.weight", [EMBD, 16], "bf16", None), ("output.weight", [EMBD, 16], "bf16", None)]
    for l in range(LAYERS):
        p = f"blk.{l}."
        out += [(p + "attn_q.weight", [EMBD, EMBD], "bf16", None), (p + "attn_norm.weight", [EMBD], "f32", None),
                (p + "ffn_gate_inp.weight", [EMBD, E], "f32", None)]
        for kind, shape in (("gate", [EMBD, FF, E]), ("up", [EMBD, FF, E]), ("down", [FF, EMBD, E])):
            if l in QUANTIZED:
                out.append((p + f"ffn_{kind}_exps.weight", shape, "nvfp4", None))
                vals = [0.001 * (l + e + 1) for e in range(E)]
                out.append((p + f"ffn_{kind}_exps.scale", [E], "f32", floats(*vals)))
                out.append((p + f"ffn_{kind}_exps.input_scale", [E], "f32", floats(*([0.01] * E))))
            else:
                out.append((p + f"ffn_{kind}_exps.weight", shape, "bf16", None))
    result = []
    for name, shape, type_, data in out:
        if name in drop:
            continue
        if name in overrides:
            type_, data = overrides[name], None
        if name == bad_scale:
            data = floats(*([0.0] * E))
        result.append((name, shape, type_, data))
    return result


def make_pack(directory, shards=2, **kw):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    table = rows(**kw)
    paths = []
    for s in range(shards):
        part = table[s::shards]
        meta = {"general.architecture": "muse-spark", "general.alignment": 32, "muse-spark.expert_count": E,
                "muse-spark.block_count": LAYERS, "split.no": s, "split.count": shards}
        path = directory / f"muse-nvfp4-{s + 1:05d}-of-{shards:05d}.gguf"
        write_gguf(path, part, meta)
        paths.append(path)
    return paths


def make_inventory(path):
    """The scale_inventory output a converter run would have been planned from (dtypes known)."""
    experts = {}
    for l in range(LAYERS):
        q = l in QUANTIZED
        slot = {"packed_weight": {"dtype": "U8" if q else "BF16"}}
        if q:
            slot.update(block_scale={"dtype": "F8_E4M3"}, global_scale={"dtype": "F32"}, input_scale={"dtype": "F32"})
        experts[str(l)] = {"gate_up": dict(slot), "down": dict(slot)}
    inv = {"format": "factory.nvfp4-scale-inventory/1", "quantized_layers": list(QUANTIZED),
           "excluded_layers": [l for l in range(LAYERS) if l not in QUANTIZED], "n_layers": LAYERS, "experts": experts}
    Path(path).write_text(json.dumps(inv))
    return path
