"""Static gate rules for an expert fill change to llama.cpp. Standard library only.

Input: the parsed patch (patchlib.parse_patch). The rules read the added lines (comments and string contents
kept where a rule needs a literal, e.g. the gate's env name or the router node name). They are heuristics over
source text: each says what it recognized, and a rule that recognizes nothing returns `inconclusive` (runtime
acceptance then decides) instead of guessing a pass.

  allowed_paths         every touched path is in SOURCE-MAP's allowed set
  protected_paths       no kernel (ggml-cpu, ggml-cuda), graph builder (llama-graph), model graph (src/models)
                        or converter edit
  plain_text_edits      no binary, mode or delete patches
  gate_env              the change reads LLAMA_EXPERT_FILL
  gate_default_off      the gate's unset value is off (fails on a recognized default-on form)
  fill_before_matmul    the fill trigger is the router output, not an expert matmul output (an eval callback
                        fires after its node computed, so keying on ffn_moe_{up,gate,down} or MUL_MAT_ID there
                        fills after the matmul already faulted the pages in)
  no_tensor_writes      no write into tensor data or the mapping (tensor_set, memcpy to ->data, PROT_WRITE,
                        MAP_PRIVATE remap, mprotect)
  no_graph_change       no new ggml graph op in the added code (the fill must not change what is computed)
"""
import re

STAGE = "native CC execution"
GATE = "LLAMA_EXPERT_FILL"
ALLOWED = (
    "src/llama-context.cpp", "src/llama-context.h", "src/llama-expert-fill.h", "src/llama-expert-fill.cpp",
    "src/CMakeLists.txt", "src/llama-cparams.h", "src/llama-mmap.cpp", "src/llama-mmap.h",
    "src/llama-model.cpp", "src/llama-model.h", "src/llama-model-loader.cpp", "src/llama-model-loader.h",
    "ggml/include/ggml-backend.h", "ggml/src/ggml-backend.cpp",
)
PROTECTED = ("ggml/src/ggml-cpu/", "ggml/src/ggml-cuda/", "src/models/", "src/llama-graph.cpp", "src/llama-graph.h",
             "gguf-py/", "conversion/", "convert_hf_to_gguf.py", "include/llama.h")
ROUTER_NAMES = ("ffn_moe_topk", "ffn_moe_argsort", "ffn_moe_probs", "ffn_moe_logits", "ffn_moe_weights")
MATMUL_NAME = re.compile(r'"ffn_moe_(?:gate_up|gate|up|down)(?:_scaled|_b)?-?"')
EVAL_HOOK = re.compile(r"\bcb_eval\b|set_eval_callback|ggml_backend_sched_eval_callback")
BEFORE_HOOK = re.compile(r"set_cpu_callback|before[_ ]node|pre[_-]?compute")
WRITES = [
    (re.compile(r"\bggml_backend_tensor_(?:set|memset|copy)\w*\s*\("), "ggml_backend_tensor_set/memset/copy"),
    (re.compile(r"\b(?:memcpy|memmove|memset|pread|read)\s*\(\s*\(?[^,;]*->data\b"), "copy into ->data"),
    (re.compile(r"->data\s*\)?\s*(?:\[[^\]]*\])?\s*(?:\+\s*[^;=]+)?\)?\s*\[[^\]]*\]\s*=[^=]"), "store through ->data"),
    (re.compile(r"\bPROT_WRITE\b"), "PROT_WRITE"),
    (re.compile(r"\bMAP_PRIVATE\b"), "MAP_PRIVATE remap"),
    (re.compile(r"\bmprotect\s*\("), "mprotect"),
]
GRAPH_OPS = re.compile(r"\bggml_(?:mul_mat\w*|mul|add\w*|sub|div|scale\w*|cpy|set_\w+|get_rows\w*|cont\w*|"
                       r"reshape\w*|view_\d+d|permute|transpose|map_custom\w*|custom_\w+|soft_max\w*|argsort\w*|"
                       r"top_k|concat|repeat\w*|build_forward_expand)\s*\(")


def check(name, status, detail, stage=STAGE):
    return {"name": name, "status": status, "stage": stage, "detail": detail}


def strip_comments(text):
    """Blank // and /* */ comments; keep string literals (rules read env and node names)."""
    pattern = r'''"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|/\*.*?\*/|//[^\n]*'''
    return re.sub(pattern, lambda m: m.group(0) if m.group(0)[0] in "\"'" else re.sub(r"[^\n]", " ", m.group(0)),
                  text, flags=re.DOTALL)


def added_code(patch_files):
    """{path: comment-stripped text of the added lines}."""
    out = {}
    for fp in patch_files:
        lines = [body for h in fp["hunks"] for tag, body in h["lines"] if tag == "+"]
        if fp["new"]:
            out[fp["new"]] = strip_comments("\n".join(lines))
    return out


def gate_default(code):
    """('off'|'on'|None, evidence) for the LLAMA_EXPERT_FILL gate in the added code."""
    on, off = [], []
    lit = re.escape(f'"{GATE}"')
    # helper(name, default, ...): the default argument
    for m in re.finditer(rf"\b\w+\s*\(\s*{lit}\s*,\s*([^,\)]+)", code):
        d = m.group(1).strip().strip('"')
        (off if d in ("0", "0L", "0u", "false", "") else on).append(m.group(0))
    # const char * X = getenv("LLAMA_EXPERT_FILL") and how X's absence is read
    for m in re.finditer(rf"(\w+)\s*=\s*(?:std::)?getenv\s*\(\s*{lit}\s*\)", code):
        x = re.escape(m.group(1))
        for p in (rf"!\s*{x}\s*\|\|", rf"\b{x}\s*==\s*(?:nullptr|NULL|0)\s*\|\|", rf"\b{x}\s*\?[^:;]*:\s*(?:true|1)\b"):
            on += [n.group(0) for n in re.finditer(p, code)]
        for p in (rf"\b{x}\s*&&", rf"\b{x}\s*!=\s*(?:nullptr|NULL|0)\s*&&", rf"\b{x}\s*\?[^:;]*:\s*(?:false|0)\b",
                  rf"if\s*\(\s*{x}\s*\)", rf"if\s*\(\s*!\s*{x}\s*\)\s*(?:\{{\s*)?return\b"):
            off += [n.group(0) for n in re.finditer(p, code)]
    # inline getenv("LLAMA_EXPERT_FILL") in an expression
    on += [m.group(0) for m in re.finditer(rf"!\s*(?:std::)?getenv\s*\(\s*{lit}\s*\)\s*\|\|", code)]
    off += [m.group(0) for m in re.finditer(rf"(?:std::)?getenv\s*\(\s*{lit}\s*\)\s*&&", code)]
    if on:
        return "on", on[:3]
    if off:
        return "off", off[:3]
    return None, []


def fill_checks(patch_files, stage=STAGE):
    out = []
    paths = sorted({p for fp in patch_files for p in (fp["old"], fp["new"]) if p})
    outside = [p for p in paths if p not in ALLOWED]
    out.append(check("allowed_paths", "fail" if outside else "pass",
                     f"outside the SOURCE-MAP allowed set: {outside}" if outside else f"touches {paths}", stage))
    protected = [p for p in paths if p.startswith(PROTECTED)]
    out.append(check("protected_paths", "fail" if protected else "pass",
                     f"edits protected files: {protected}" if protected else
                     "no kernel, graph builder, model graph or converter edits", stage))
    odd = [fp["new"] or fp["old"] for fp in patch_files if fp["binary"] or fp["mode_change"] or fp["deleted"]]
    out.append(check("plain_text_edits", "fail" if odd else "pass", odd or "text edits only", stage))

    code = added_code(patch_files)
    allcode = "\n".join(code.values())
    out.append(check("gate_env", "pass" if f'"{GATE}"' in allcode else "fail",
                     f'reads "{GATE}"' if f'"{GATE}"' in allcode else f'the change never reads "{GATE}": no off switch',
                     stage))
    state, evidence = gate_default(allcode)
    out.append(check("gate_default_off", {"off": "pass", "on": "fail", None: "inconclusive"}[state],
                     {"off": f"unset reads as off: {evidence}",
                      "on": f"unset (or absent) {GATE} turns the fill on: {evidence}",
                      None: f"no recognized {GATE} parse; runtime acceptance (no marker without the gate) decides"}[state],
                     stage))

    after = sorted({m.group(0) for m in MATMUL_NAME.finditer(allcode)})
    eval_hook = bool(EVAL_HOOK.search(allcode))
    if eval_hook and "GGML_OP_MUL_MAT_ID" in allcode and not BEFORE_HOOK.search(allcode):
        after.append("GGML_OP_MUL_MAT_ID in an eval callback")
    router = sorted({n for n in ROUTER_NAMES if f'"{n}' in allcode})
    if after:
        out.append(check("fill_before_matmul", "fail", f"the fill is keyed on an expert matmul node {after}: an eval "
                         "callback runs after its node computed, so the matmul has already faulted the pages in",
                         stage))
    elif router or BEFORE_HOOK.search(allcode):
        out.append(check("fill_before_matmul", "pass", f"keyed on the router output {router}" if router else
                         "a before-node scheduler hook", stage))
    else:
        out.append(check("fill_before_matmul", "inconclusive", "no recognized trigger (router node name or "
                         "before-node hook); runtime acceptance decides", stage))

    writes = sorted({f"{p}: {label}" for p, text in code.items() for rx, label in WRITES if rx.search(text)})
    out.append(check("no_tensor_writes", "fail" if writes else "pass",
                     f"writes tensor data or the mapping: {writes}" if writes else
                     "no tensor_set, no store through ->data, no writable or private remap", stage))
    ops = sorted({f"{p}: {m.group(0).rstrip('( ')}" for p, text in code.items() for m in GRAPH_OPS.finditer(text)})
    out.append(check("no_graph_change", "fail" if ops else "pass",
                     f"adds graph ops (changes what is computed): {ops}" if ops else "no new ggml graph op", stage))
    return out
