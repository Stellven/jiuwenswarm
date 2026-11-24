"""Verifier's own model of stock llama-quantize (llama.cpp 9048bad8): argv parsing and per-tensor type choice.

Written from tools/quantize/quantize.cpp (llama_quantize, parse_tensor_type, parse_ggml_type, QUANT_OPTIONS) and
src/llama-quant.cpp (tensor_allows_quantization, llama_tensor_get_type, tensor_type_fallback). It is independent
of the recipe planner on purpose: the verifier predicts what the tool will write from the argv alone.

Facts it encodes:
- flags must precede the positionals; an unknown `--flag` makes the tool print usage and exit;
- positionals are `input [output] ftype [nthreads]`; with `--keep-split` a trailing `.gguf` is cut from output;
- `--tensor-type NAME=TYPE`: NAME is lower-cased, compiled with std::regex (ECMAScript) and matched with
  regex_search (substring, so anchor with ^...$); the first matching pattern wins;
- overrides only apply to tensors stock allows to quantize (n_dims >= 2, name ends in `weight`, no
  `_norm.weight`, not `ffn_gate_inp.weight`, ...); other tensors are copied at their type;
- `--token-embedding-type` and `--output-tensor-type` are applied before any pattern;
- a tensor whose chosen type equals its type is copied byte for byte, otherwise it is converted (requires
  `--allow-requantize` when the source is quantized);
- the fallback when ne[0] is not whole blocks (tensor_type_fallback).
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gguf_pack import TYPE_ID, block_of  # noqa: E402

VALUE_FLAGS = {"--output-tensor-type", "--token-embedding-type", "--tensor-type", "--tensor-type-file",
               "--prune-layers", "--override-kv", "--imatrix", "--include-weights", "--exclude-weights",
               "--max-buffer-size"}
BARE_FLAGS = {"--allow-requantize", "--leave-output-tensor", "--pure", "--dry-run", "--keep-split"}
FTYPES = {"Q1_0", "Q2_0", "Q4_0", "Q4_1", "MXFP4_MOE", "Q5_0", "Q5_1", "IQ2_XXS", "IQ2_XS", "IQ2_S", "IQ2_M",
          "IQ1_S", "IQ1_M", "TQ1_0", "TQ2_0", "Q2_K", "Q2_K_S", "IQ3_XXS", "IQ3_S", "IQ3_M", "Q3_K", "IQ3_XS",
          "Q3_K_S", "Q3_K_M", "Q3_K_L", "IQ4_NL", "IQ4_XS", "Q4_K", "Q4_K_S", "Q4_K_M", "Q5_K", "Q5_K_S",
          "Q5_K_M", "Q6_K", "Q8_0", "F16", "BF16", "F32", "COPY"}
UNQUANTIZED_FTYPES = {"F16", "BF16", "F32", "COPY"}
NO_QUANT = ("_norm.weight", "ffn_gate_inp.weight", "ffn_gate_tid2eid.weight", "engram_gate.weight", "altup",
            "laurel", "per_layer_model_proj", "ssm_conv1d", "shortconv.conv.weight", "conv2d_spatial.weight",
            "conv_dw", "indexer.k_proj.weight", "indexer.q_proj.weight", "time_mix_first.weight",
            "time_mix_w0.weight")
FALLBACK = {**{t: "iq4_nl" for t in ("iq1_s", "iq1_m", "iq2_xxs", "iq2_xs", "iq2_s", "iq3_xxs", "iq3_s", "iq4_xs")},
            **{t: "q4_0" for t in ("q2_0", "q2_k", "q3_k", "tq1_0", "tq2_0")},
            "q4_k": "q5_0", "q5_k": "q5_1", "q6_k": "q8_0"}


def parse_argv(argv):
    """Return the parsed call or raise ValueError where stock would print usage or refuse."""
    if not argv:
        raise ValueError("empty argv")
    out = {"flags": set(), "tensor_types": [], "imatrix": None, "include": [], "exclude": [], "prune": None,
           "token_embedding_type": None, "output_tensor_type": None}
    i = 1
    while i < len(argv) and argv[i].startswith("--"):
        flag = argv[i]
        if flag in BARE_FLAGS:
            out["flags"].add(flag)
        elif flag in VALUE_FLAGS:
            if i + 1 >= len(argv):
                raise ValueError(f"{flag} has no value")
            value = argv[i + 1]
            i += 1
            if flag == "--tensor-type":
                name, sep, qtype = value.partition("=")
                if not sep or not name or not qtype:
                    raise ValueError(f"malformed --tensor-type {value!r}")
                if qtype.lower() not in TYPE_ID:
                    raise ValueError(f"invalid ggml type {qtype!r} in --tensor-type")
                try:
                    pattern = re.compile(name.lower())
                except re.error as exc:
                    raise ValueError(f"pattern {name!r} does not compile: {exc}") from exc
                out["tensor_types"].append((pattern, qtype.lower()))
            elif flag == "--tensor-type-file":
                raise ValueError("--tensor-type-file is not modelled; inline the pins with --tensor-type")
            elif flag in ("--token-embedding-type", "--output-tensor-type"):
                if value.lower() not in TYPE_ID:
                    raise ValueError(f"invalid ggml type {value!r} for {flag}")
                out[flag[2:].replace("-", "_")] = value.lower()
            elif flag == "--imatrix":
                out["imatrix"] = value
            elif flag == "--include-weights":
                out["include"].append(value)
            elif flag == "--exclude-weights":
                out["exclude"].append(value)
            elif flag == "--prune-layers":
                out["prune"] = [int(x) for x in value.split(",")]
            out["flags"].add(flag)
        else:
            raise ValueError(f"unknown flag {flag} (stock prints usage)")
        i += 1
    if out["include"] and out["exclude"]:
        raise ValueError("--include-weights and --exclude-weights cannot be used together")
    rest = argv[i:]
    if len(rest) < 2:
        raise ValueError("missing input or file type")
    out["input"] = rest[0]
    if rest[1].upper() in FTYPES:
        out["output"], out["ftype"], extra = None, rest[1].upper(), rest[2:]
    else:
        if len(rest) < 3 or rest[2].upper() not in FTYPES:
            raise ValueError(f"invalid or missing file type after output {rest[1]!r}")
        out["output"], out["ftype"], extra = rest[1], rest[2].upper(), rest[3:]
    if len(extra) > 1 or (extra and not extra[0].isdigit()):
        raise ValueError(f"unexpected trailing arguments {extra}")
    if out["output"] and "--keep-split" in out["flags"] and out["output"].endswith(".gguf"):
        out["output_prefix"] = out["output"][:-5]
    return out


def allows_quantization(name, shape, leave_output=False):
    if len(shape) < 2 or not name.endswith("weight"):
        return False
    if leave_output and name == "output.weight":
        return False
    return not any(token in name for token in NO_QUANT)


def fallback(type_, ncols):
    block = block_of(type_)[0]
    if ncols % block == 0:
        return type_
    chosen = FALLBACK.get(type_, type_ if block <= 32 else None)
    if chosen is None:
        raise ValueError(f"stock has no fallback for {type_}")
    return chosen if ncols % block_of(chosen)[0] == 0 else "f16"


def predict(call, name, shape, source_type):
    """(type stock writes, how) for one tensor; how is copy, pinned, token/output flag or mixture."""
    if call["ftype"] in UNQUANTIZED_FTYPES or not allows_quantization(
            name, shape, "--leave-output-tensor" in call["flags"]):
        return source_type, "not quantizable: copied"
    if call["token_embedding_type"] and name in ("token_embd.weight", "per_layer_token_embd.weight"):
        if not (name == "per_layer_token_embd.weight" and any(p.search(name) for p, _ in call["tensor_types"])):
            return call["token_embedding_type"], "--token-embedding-type"
    if call["output_tensor_type"] and name == "output.weight":
        return call["output_tensor_type"], "--output-tensor-type"
    for pattern, qtype in call["tensor_types"]:
        if pattern.search(name):
            return fallback(qtype, shape[0]), "pinned by " + pattern.pattern
    return None, "unpinned: stock mixture for " + call["ftype"]
