"""Tiny Muse Spark checkpoints in the real Hugging Face / ModelOpt layout, deterministic (seed 1234).

Needs torch and safetensors (the conversion venv: python -m venv .venv; .venv/bin/pip install torch
safetensors numpy transformers; pip install -e <llama.cpp>/gguf-py).

  python tiny_checkpoint.py --out DIR --tokenizer-dir REF [--config CONFIG.json] [--only bf16,nvfp4,deqref]

  DIR/bf16/    random weights in BF16; experts stacked [E, 2I, M] (gate rows first) and [E, M, I]
  DIR/nvfp4/   the same weights, experts of layers 1..L-2 in ModelOpt NVFP4: U8 nibble-packed [E, rows, in/2],
               F8_E4M3 block scale [E, rows, in/16], F32 weight_scale_2 [E, 2] (gate, up) or [E] (down),
               F32 input_scale alike; layer 0, the last layer, self_attn and lm_head excluded (BF16);
               three shards and an index, like the real checkpoint
  DIR/deqref/  F32 reference: expert weights are the exact dequantized NVFP4 values, everything else upcast

REF holds tokenizer.json, tokenizer_config.json, special_tokens_map.json, chat_template.jinja and
generation_config.json of the real model (and hf_quant_config.json if present). CONFIG is any Muse Spark config
(tiny-random or the real one); the text dimensions are overwritten with the tiny ones below.
Per-expert and per-half magnitudes vary by e^N(0,1), so every scale_2 differs and a gate/up or column mix-up shows.
"""
import argparse
import json
from pathlib import Path
import shutil

import torch
from safetensors.torch import save_file

H, M, I, E, K, L = 512, 256, 256, 16, 4, 4
NH, NKV, HD = 8, 2, 64
E2M1 = torch.tensor([0.0, 0.5, 1.0, 1.5, 2.0, 3.0, 4.0, 6.0])
TOKENIZER_FILES = ("tokenizer.json", "tokenizer_config.json", "special_tokens_map.json", "chat_template.jinja",
                   "generation_config.json")
PFX = "model.language_model."


def nvfp4_quant(w):
    """[rows, cols] f32 -> packed u8 [rows, cols/2], block scale f8 [rows, cols/16], scale2 f32, dequantized f32."""
    rows, cols = w.shape
    scale2 = (w.abs().max() / (6.0 * 448.0)).float()
    wb = w.reshape(rows, cols // 16, 16)
    bs = (wb.abs().amax(-1) / (6.0 * scale2)).clamp(max=448.0).to(torch.float8_e4m3fn)
    denom = (bs.float() * scale2).unsqueeze(-1)
    q = torch.where(denom > 0, wb / denom, torch.zeros_like(wb))
    idx = (q.abs().clamp(max=6.0).unsqueeze(-1) - E2M1).abs().argmin(-1)
    sign = (q < 0) & (idx > 0)
    code = (idx | (sign.long() << 3)).to(torch.uint8).reshape(rows, cols)
    packed = (code[:, 0::2] | (code[:, 1::2] << 4)).contiguous()  # element 2j low nibble, 2j+1 high
    deq = (E2M1[idx] * torch.where(sign, -1.0, 1.0)) * denom
    return packed, bs, scale2, deq.reshape(rows, cols)


def bf(t):
    return t.to(torch.bfloat16)


def build_weights(vocab):
    torch.manual_seed(1234)
    base, experts = {}, {}
    base[PFX + "embed_tokens.weight"] = bf(torch.randn(vocab, H))
    base[PFX + "norm.weight"] = bf(1.0 + 0.1 * torch.randn(H))
    base["lm_head.weight"] = bf(torch.randn(vocab, H) / H ** 0.5)
    for l in range(L):
        p = f"{PFX}layers.{l}."
        for n in ("input_layernorm", "pre_feedforward_layernorm", "post_feedforward_layernorm"):
            base[p + n + ".weight"] = bf(0.1 * torch.randn(H))
        base[p + "self_attn.q_proj.weight"] = bf(torch.randn(NH * HD, H) / H ** 0.5)
        base[p + "self_attn.k_proj.weight"] = bf(torch.randn(NKV * HD, H) / H ** 0.5)
        base[p + "self_attn.v_proj.weight"] = bf(torch.randn(NKV * HD, H) / H ** 0.5)
        base[p + "self_attn.o_proj.weight"] = bf(torch.randn(H, NH * HD) / (NH * HD) ** 0.5)
        base[p + "self_attn.gate_proj.weight"] = bf(torch.randn(NH * HD, H) / H ** 0.5)
        base[p + "post_attention_residual_gate.gate"] = bf(torch.randn(H))
        base[p + "post_feedforward_residual_gate.gate"] = bf(torch.randn(H))
        base[p + "mlp.gate.weight"] = torch.randn(E, H) / H ** 0.5 * 4.0
        base[p + "mlp.gate.e_score_correction_bias"] = 0.1 * torch.randn(E)
        base[p + "mlp.pre_expert_proj.weight"] = bf(torch.randn(M, H) / H ** 0.5)
        base[p + "mlp.post_expert_proj.weight"] = bf(torch.randn(H, M) / M ** 0.5)
        base[p + "mlp.pre_expert_norm.weight"] = bf(0.1 * torch.randn(M))
        base[p + "mlp.experts.post_expert_norm.weight"] = bf(0.1 * torch.randn(M))
        g = torch.randn(E, I, M) / M ** 0.5 * torch.exp(torch.randn(E, 1, 1))
        u = torch.randn(E, I, M) / M ** 0.5 * torch.exp(torch.randn(E, 1, 1))
        d = torch.randn(E, M, I) / I ** 0.5 * torch.exp(torch.randn(E, 1, 1))
        experts[(l, "gate_up")] = bf(torch.cat([g, u], 1)).float()
        experts[(l, "down")] = bf(d).float()
    return base, experts


def tiny_config(config_path):
    cfg = json.loads(Path(config_path).read_text(encoding="utf-8"))
    cfg.pop("quantization_config", None)
    t = cfg["text_config"]
    t.pop("quantization_config", None)
    lt = ["sliding_attention", "full_attention", "sliding_attention", "sliding_attention"][:L]
    t.update(hidden_size=H, head_dim=HD, num_attention_heads=NH, num_key_value_heads=NKV, intermediate_size=2 * H,
             moe_hidden_size=M, moe_intermediate_size=I, num_local_experts=E, num_experts_per_tok=K,
             num_hidden_layers=L, layer_types=lt,
             layer_rope_theta=[500000.0 if x == "sliding_attention" else 0 for x in lt], mlp_layer_types=["sparse"] * L)
    if "audio_config" in cfg:
        cfg["audio_config"]["out_hidden_size"] = H
    return cfg


def write(d, tensors, ref, cfg, shards=1):
    d.mkdir(parents=True, exist_ok=True)
    names = sorted(tensors)
    if shards == 1:
        save_file({k: tensors[k].contiguous() for k in names}, str(d / "model.safetensors"), metadata={"format": "pt"})
    else:
        weight_map = {}
        for i in range(shards):
            chunk = names[i::shards]
            fn = f"model-{i + 1:05d}-of-{shards:05d}.safetensors"
            save_file({k: tensors[k].contiguous() for k in chunk}, str(d / fn), metadata={"format": "pt"})
            weight_map.update({k: fn for k in chunk})
        (d / "model.safetensors.index.json").write_text(json.dumps({"metadata": {}, "weight_map": weight_map}, indent=1))
    for f in TOKENIZER_FILES:
        if (ref / f).is_file():
            shutil.copy(ref / f, d / f)
    (d / "config.json").write_text(json.dumps(cfg, indent=1))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True)
    ap.add_argument("--tokenizer-dir", required=True)
    ap.add_argument("--config", help="Muse Spark config.json to start from (default: TOKENIZER_DIR/config.json)")
    ap.add_argument("--only", default="bf16,nvfp4,deqref")
    args = ap.parse_args()
    root, ref = Path(args.out), Path(args.tokenizer_dir)
    which = set(args.only.split(","))
    cfg = tiny_config(args.config or ref / "config.json")
    vocab = cfg["text_config"].get("vocab_size", 202048)
    base, experts = build_weights(vocab)

    if "bf16" in which:
        a = dict(base)
        for (l, k), w in experts.items():
            a[f"{PFX}layers.{l}.mlp.experts.{k}_proj"] = bf(w)
        write(root / "bf16", a, ref, cfg)

    b, c, excluded = dict(base), {k: v.float() for k, v in base.items()}, {0, L - 1}
    for (l, k), w in experts.items():
        n = f"{PFX}layers.{l}.mlp.experts.{k}_proj"
        if l in excluded:
            b[n], c[n] = bf(w), w.clone()
            continue
        halves = [w[:, :I], w[:, I:]] if k == "gate_up" else [w]
        packed, scale, scale2, deq = [], [], [], []
        for e in range(E):
            q = [nvfp4_quant(h[e]) for h in halves]
            packed.append(torch.cat([x[0] for x in q], 0))
            scale.append(torch.cat([x[1].view(torch.uint8) for x in q], 0).view(torch.float8_e4m3fn))
            scale2.append(torch.stack([x[2] for x in q]))
            deq.append(torch.cat([x[3] for x in q], 0))
        b[n] = torch.stack(packed)
        b[n + "_weight_scale"] = torch.stack(scale)
        s2 = torch.stack(scale2).float()
        b[n + "_weight_scale_2"] = s2 if k == "gate_up" else s2[:, 0].contiguous()
        ins = (0.5 + torch.rand(E, len(halves))) * 0.01
        b[n + "_input_scale"] = ins if k == "gate_up" else ins[:, 0].contiguous()
        c[n] = torch.stack(deq)
    exclude = ["layers.0.", f"layers.{L - 1}.", "self_attn", "lm_head"]
    if "nvfp4" in which:
        qcfg = dict(cfg, quantization_config={"quant_method": "modelopt", "quant_algo": "NVFP4", "group_size": 16,
                                              "exclude_modules": exclude})
        write(root / "nvfp4", b, ref, qcfg, shards=3)
        hq = {"quant_method": "modelopt", "quantization": {"quant_algo": "NVFP4", "group_size": 16,
                                                            "kv_cache_quant_algo": None, "exclude_modules": exclude}}
        (root / "nvfp4" / "hf_quant_config.json").write_text(json.dumps(hq, indent=1))
    if "deqref" in which:
        write(root / "deqref", c, ref, dict(cfg, dtype="float32"))
    print(json.dumps({"out": str(root), "written": sorted(which), "layers": L, "experts": E,
                      "quantized_layers": [l for l in range(L) if l not in excluded]}))


if __name__ == "__main__":
    main()
