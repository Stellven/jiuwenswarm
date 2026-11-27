"""Read GGUF headers (metadata + tensor table, no weights) to size the routed experts.

Used for the M.expert_cache_hit estimate: bytes of routed-expert weights one token needs
(sum over layers of expert_tensor_bytes / expert_count * expert_used_count). Tensor sizes come
from offset differences, so no table of quantization block sizes is needed.
"""
import os, re, struct

_SCALAR = {0: "<B", 1: "<b", 2: "<H", 3: "<h", 4: "<I", 5: "<i", 6: "<f", 7: "<?", 10: "<Q", 11: "<q", 12: "<d"}


class _Reader:
    def __init__(self, f):
        self.f = f

    def unpack(self, fmt):
        n = struct.calcsize(fmt)
        b = self.f.read(n)
        if len(b) != n:
            raise ValueError("truncated GGUF header")
        return struct.unpack(fmt, b)[0]

    def string(self):
        n = self.unpack("<Q")
        return self.f.read(n).decode("utf-8", errors="replace")

    def value(self, vtype):
        if vtype in _SCALAR:
            return self.unpack(_SCALAR[vtype])
        if vtype == 8:
            return self.string()
        if vtype == 9:
            etype, n = self.unpack("<I"), self.unpack("<Q")
            if etype in _SCALAR and n > 64:  # long arrays (vocab scores, token types): skip the bytes
                self.f.seek(struct.calcsize(_SCALAR[etype]) * n, 1)
                return None
            if etype == 8 and n > 64:
                for _ in range(n):
                    self.f.seek(self.unpack("<Q"), 1)
                return None
            return [self.value(etype) for _ in range(n)]
        raise ValueError(f"unknown GGUF value type {vtype}")


def read_header(path):
    """Return (metadata dict, [(name, dims, ggml_type, size_bytes)]) for one GGUF file."""
    size = os.path.getsize(path)
    with open(path, "rb") as f:
        r = _Reader(f)
        if f.read(4) != b"GGUF":
            raise ValueError(f"not a GGUF file: {path}")
        version = r.unpack("<I")
        n_tensors, n_kv = r.unpack("<Q"), r.unpack("<Q")
        meta = {"_version": version}
        for _ in range(n_kv):
            key = r.string()
            meta[key] = r.value(r.unpack("<I"))
        infos = []
        for _ in range(n_tensors):
            name = r.string()
            nd = r.unpack("<I")
            dims = [r.unpack("<Q") for _ in range(nd)]
            gtype, offset = r.unpack("<I"), r.unpack("<Q")
            infos.append((name, dims, gtype, offset))
        align = int(meta.get("general.alignment", 32) or 32)
        data_start = (f.tell() + align - 1) // align * align
    order = sorted(infos, key=lambda t: t[3])
    out = []
    for i, (name, dims, gtype, offset) in enumerate(order):
        end = order[i + 1][3] if i + 1 < len(order) else size - data_start
        out.append((name, dims, gtype, end - offset))
    return meta, out


def expert_summary(files):
    """Routed-expert bytes per generated token for a (possibly split) GGUF checkpoint."""
    meta, tensors = {}, []
    for p in files:
        m, t = read_header(p)
        for k, v in m.items():
            meta.setdefault(k, v)
        tensors += t
    arch = meta.get("general.architecture")
    def key(suffix):
        if arch and f"{arch}.{suffix}" in meta:
            return meta[f"{arch}.{suffix}"]
        return next((v for k, v in meta.items() if k.endswith("." + suffix)), None)
    n_exp, n_used = key("expert_count"), key("expert_used_count")
    routed = [(n, s) for n, d, g, s in tensors if re.search(r"\.ffn_\w*_exps\.", n)]
    shared = [(n, s) for n, d, g, s in tensors if re.search(r"\.ffn_\w*_shexp\.", n)]
    if not n_exp or not n_used or not routed:
        return {"architecture": arch, "expert_count": n_exp, "expert_used_count": n_used,
                "routed_expert_tensors": len(routed), "routed_bytes_per_token": None}
    total = sum(s for _, s in routed)
    layers = {re.match(r"blk\.(\d+)\.", n).group(1) for n, _ in routed if re.match(r"blk\.(\d+)\.", n)}
    return {"architecture": arch, "expert_count": int(n_exp), "expert_used_count": int(n_used),
            "moe_layers": len(layers), "routed_expert_tensors": len(routed),
            "routed_expert_gb": round(total / 1e9, 2), "shared_expert_gb": round(sum(s for _, s in shared) / 1e9, 2),
            "routed_bytes_per_token": total / int(n_exp) * int(n_used)}
