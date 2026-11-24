#!/usr/bin/env python3
"""Read the headers of GGUF model files: the metadata and, for every tensor, its name, shape, type and size.
Reads only the header of each file (a few megabytes); the weights themselves are not read. Standard library only.

    python3 gguf_header.py OUT.json FILE.gguf [FILE.gguf ...]
"""
import json
import os
import struct
import sys

TYPES = {0: "F32", 1: "F16", 2: "Q4_0", 3: "Q4_1", 6: "Q5_0", 7: "Q5_1", 8: "Q8_0", 9: "Q8_1", 10: "Q2_K", 11: "Q3_K",
         12: "Q4_K", 13: "Q5_K", 14: "Q6_K", 15: "Q8_K", 16: "IQ2_XXS", 17: "IQ2_XS", 18: "IQ3_XXS", 19: "IQ1_S",
         20: "IQ4_NL", 21: "IQ3_S", 22: "IQ2_S", 23: "IQ4_XS", 24: "I8", 25: "I16", 26: "I32", 27: "I64", 28: "F64",
         29: "IQ1_M", 30: "BF16", 34: "TQ1_0", 35: "TQ2_0"}
SCALAR = {0: "<B", 1: "<b", 2: "<H", 3: "<h", 4: "<I", 5: "<i", 6: "<f", 7: "<?", 10: "<Q", 11: "<q", 12: "<d"}


def read(f, fmt):
    n = struct.calcsize(fmt)
    return struct.unpack(fmt, f.read(n))[0]


def string(f):
    n = read(f, "<Q")
    return f.read(n).decode("utf-8", "replace")


def value(f, t, keep):
    if t in SCALAR:
        return read(f, SCALAR[t])
    if t == 8:
        s = string(f)
        return s if keep else None
    if t == 9:
        it, n = read(f, "<I"), read(f, "<Q")
        if it in SCALAR and n > 64:                       # a long numeric array: skip it in one step
            f.seek(n * struct.calcsize(SCALAR[it]), 1)
            return {"array_of": it, "length": n}
        items = [value(f, it, keep and n <= 64) for _ in range(n)]
        return items if n <= 64 else {"array_of": it, "length": n}
    raise ValueError("unknown value type %d" % t)


def header(path):
    out = {"file": os.path.basename(path), "bytes": os.path.getsize(path)}
    with open(path, "rb") as f:
        if f.read(4) != b"GGUF":
            raise ValueError("not a GGUF file")
        out["version"] = read(f, "<I")
        n_tensors, n_kv = read(f, "<Q"), read(f, "<Q")
        kv = {}
        for _ in range(n_kv):
            key = string(f)
            t = read(f, "<I")
            v = value(f, t, True)
            if isinstance(v, str) and len(v) > 300:          # a chat template or the like: its length is enough
                v = {"text_of_length": len(v)}
            kv[key] = v
        out["metadata"] = kv
        tensors = []
        for _ in range(n_tensors):
            name = string(f)
            nd = read(f, "<I")
            dims = [read(f, "<Q") for _ in range(nd)]
            tt, off = read(f, "<I"), read(f, "<Q")
            tensors.append({"name": name, "shape": dims, "type": TYPES.get(tt, str(tt)), "offset": off})
        align = kv.get("general.alignment", 32)
        data_start = (f.tell() + align - 1) // align * align
        out["header_bytes"] = data_start
        order = sorted(range(len(tensors)), key=lambda i: tensors[i]["offset"])
        for a, b in zip(order, order[1:] + [None]):
            end = tensors[b]["offset"] if b is not None else out["bytes"] - data_start
            tensors[a]["bytes"] = end - tensors[a]["offset"]
        for t in tensors:
            t.pop("offset")
        out["tensors"] = tensors
    return out


def main():
    res = [header(p) for p in sys.argv[2:]]
    with open(sys.argv[1], "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    for r in res:
        print("%s: %.1f GB, header %.1f MB, %d metadata keys, %d tensors" % (
            r["file"], r["bytes"] / 1e9, r["header_bytes"] / 1e6, len(r["metadata"]), len(r["tensors"])))


if __name__ == "__main__":
    main()
