# SAMPLE (labelled; the pattern of conversion/base.py `_mxfp4_expert_tensor`, shown generically):
# hand the GGUF writer a lazy tensor so the bytes are produced only when that tensor is written.
import numpy as np
import gguf  # from the tree's gguf-py


def lazy_stacked(loaders, rows, out_bytes_per_row, convert_one):
    """loaders: per-item zero-arg callables (e.g. self.model_tensors[name]); convert_one(item) -> uint8 [rows, out_bytes_per_row]."""
    shape = (len(loaders), rows, out_bytes_per_row)       # meta only: nothing is read here

    def load(fns):                                         # runs at write time, one tensor at a time
        out = np.empty(shape, dtype=np.uint8)
        for i, fn in enumerate(fns):
            out[i] = convert_one(fn())
        return out

    # loaders go through `args`, not the closure, so `func` has LazyBase's single-argument shape
    return gguf.LazyNumpyTensor(meta=gguf.LazyNumpyTensor.meta_with_dtype_and_shape(np.uint8, shape),
                                args=(loaders,), func=load)

# Then: self.gguf_writer.add_tensor(new_name, lazy, raw_dtype=gguf.GGMLQuantizationType.<TYPE>)
# Anti-pattern: building np.stack([...]) in the loop that walks the layers keeps every layer's bytes
# alive until gguf_writer finishes, because the writer holds all added tensors until the final write.
