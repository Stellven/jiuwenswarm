# SAMPLE (labelled; illustrates indexing only, not the converter change):
# a stacked expert tensor holds two projections along dim 1, and its global scale holds one column per half.
import torch

E, I, M = 4, 8, 32                                   # experts, rows per half, input width
packed = torch.randint(0, 256, (E, 2 * I, M // 2), dtype=torch.uint8)   # U8, two FP4 codes per byte
block = torch.rand(E, 2 * I, M // 16).to(torch.float8_e4m3fn)          # one E4M3 scale per 16 inputs
scale2 = torch.rand(E, 2)                                                # [E, 2]: column per half

halves = {"first": (0, I, 0), "second": (I, 2 * I, 1)}  # (row start, row end, scale_2 column)
for label, (r0, r1, col) in halves.items():
    w = packed[:, r0:r1]          # rows of this half, every expert: [E, I, M/2]
    s = block[:, r0:r1]           # the SAME rows of the block scale:  [E, I, M/16]
    s2 = scale2[:, col]           # this half's own global scale:      [E]
    one = (w[0], s[0])            # one expert: what a per-expert packer takes
    print(label, tuple(w.shape), tuple(s.shape), tuple(s2.shape), tuple(one[0].shape))

# Do not reduce scale2 over its columns (sum/mean): the two halves were quantized separately.
# A [E] vector (down-style) is used as is: scale2_down[:, None] is not needed for an [E] .scale tensor.
