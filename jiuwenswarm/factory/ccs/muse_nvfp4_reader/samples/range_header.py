# SAMPLE (labelled; adapt, do not paste blindly): read one safetensors header without the tensor data.
# A shard is: 8-byte little-endian header length N, N bytes of JSON {name: {dtype, shape, data_offsets}}, data.
import json
import struct
import urllib.request


def header_from_url(url):
    def ranged(start, end):  # inclusive byte range; HF resolve URLs honour Range
        req = urllib.request.Request(url, headers={"Range": f"bytes={start}-{end}"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.read()
    n = struct.unpack("<Q", ranged(0, 7))[0]
    return json.loads(ranged(8, 8 + n - 1))


def header_from_file(path):
    with open(path, "rb") as f:
        n = struct.unpack("<Q", f.read(8))[0]
        return json.loads(f.read(n))


if __name__ == "__main__":
    import sys
    src = sys.argv[1]
    h = header_from_url(src) if src.startswith("http") else header_from_file(src)
    h.pop("__metadata__", None)
    for name, meta in sorted(h.items()):
        if ".experts." in name:          # the stacked expert planes and their scales
            print(f"{meta['dtype']:8s} {str(meta['shape']):22s} {name}")
