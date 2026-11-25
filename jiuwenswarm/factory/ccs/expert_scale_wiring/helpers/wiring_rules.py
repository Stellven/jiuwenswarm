"""Static gate rules for an expert scale wiring change to the Muse graph. Standard library only.

Input: the patch, the pre- and post-image of src/models/muse-spark.cpp and the text of src/llama-graph.h
(all from the checkout's HEAD, or stock copies in the capsule tests). The rules map each argument of the
Muse `build_moe_ffn(...)` call to the parameter it binds in the declaration the call resolves to, then check
that up_exps_s, gate_exps_s and down_exps_s bind the layer's own loaded scale tensors and nothing else moved.
Each scale argument must be the member expression `model.layers[il].ffn_{up,gate,down}_exps_s` itself (whitespace
aside); a local alias would be new code outside the call and fails edits_confined_to_call anyway.
"""
import re

STAGE = "native CC execution"
MODEL_FILE = "src/models/muse-spark.cpp"
PROTECTED = ("ggml/", "gguf-py/", "include/", "conversion/", "common/", "tools/", "convert_hf_to_gguf.py")
SCALES = {"up_exps_s": "ffn_up_exps_s", "gate_exps_s": "ffn_gate_exps_s", "down_exps_s": "ffn_down_exps_s"}


def check(name, status, detail, stage=STAGE):
    return {"name": name, "status": status, "stage": stage, "detail": detail}


def strip_comments(text):
    """Blank comments and string literals, keeping offsets (so spans map back to the file)."""
    pattern = r'''"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|/\*.*?\*/|//[^\n]*'''

    def blank(m):
        s = m.group(0)
        if s.startswith(("/", )):
            return re.sub(r"[^\n]", " ", s)
        return s[0] + re.sub(r"[^\n]", " ", s[1:-1]) + s[-1]
    return re.sub(pattern, blank, text, flags=re.DOTALL)


def calls(text, name="build_moe_ffn"):
    """[(start, end, [arg, ...])] for each call or declaration `name(...)`; whitespace in args collapsed."""
    code = strip_comments(text)
    out = []
    for m in re.finditer(rf"\b{name}\s*\(", code):
        depth, i, args, cur = 1, m.end(), [], m.end()
        while i < len(code) and depth:
            ch = code[i]
            if ch in "([{":
                depth += 1
            elif ch in ")]}":
                depth -= 1
            elif ch == "," and depth == 1:
                args.append(code[cur:i])
                cur = i + 1
            i += 1
        args.append(code[cur:i - 1])
        out.append((m.start(), i, [re.sub(r"\s+", " ", a).strip() for a in args if a.strip() or args != [a]]))
    return out


def declarations(header):
    """Parameter-name lists of every `ggml_tensor * build_moe_ffn(` declaration in llama-graph.h."""
    decls = []
    for start, end, params in calls(header):
        if not re.search(r"ggml_tensor\s*\*\s*$", strip_comments(header)[max(0, start - 40):start]):
            continue
        names = []
        for p in params:
            p = p.split("=")[0].strip()
            m = re.search(r"([A-Za-z_]\w*)$", p)
            names.append(m.group(1) if m else p)
        decls.append(names)
    return decls


def resolve(decls, args):
    """The declaration the call binds to: enough parameters, and LLM_FFN_* lands on type_op."""
    for names in decls:
        if len(args) > len(names) or "type_op" not in names:
            continue
        op = names.index("type_op")
        if op < len(args) and args[op].startswith("LLM_FFN_"):
            return names
    return None


def wiring_checks(patch_files, pre_text, post_text, header_text, stage=STAGE):
    out = []
    paths = sorted({p for fp in patch_files for p in (fp["old"], fp["new"]) if p})
    outside = [p for p in paths if p != MODEL_FILE]
    out.append(check("allowed_paths", "fail" if outside else "pass",
                     f"outside {MODEL_FILE}: {outside}" if outside else f"touches {paths}", stage))
    protected = [p for p in paths if p.startswith(PROTECTED)]
    out.append(check("protected_paths", "fail" if protected else "pass",
                     f"edits protected files: {protected}" if protected else "no ggml, gguf-py or converter edits", stage))
    odd = [fp["new"] or fp["old"] for fp in patch_files if fp["binary"] or fp["mode_change"] or fp["deleted"]]
    out.append(check("plain_text_edits", "fail" if odd else "pass", odd or "text edits only", stage))
    if pre_text is None or post_text is None:
        out.append(check("moe_call", "fail", f"{MODEL_FILE} is not changed by the patch or not in HEAD", stage))
        return out
    pre_calls, post_calls = calls(pre_text), calls(post_text)
    if len(pre_calls) != 1 or len(post_calls) != 1:
        out.append(check("moe_call", "fail", f"expected one build_moe_ffn call, found {len(pre_calls)} before and "
                         f"{len(post_calls)} after", stage))
        return out
    (p0, p1, pre_args), (q0, q1, post_args) = pre_calls[0], post_calls[0]
    decls = declarations(header_text or "")
    names = resolve(decls, post_args)
    if names is None:
        out.append(check("moe_call", "fail", f"the call ({len(post_args)} args) matches no build_moe_ffn declaration "
                         f"in src/llama-graph.h ({[len(d) for d in decls]} params)", stage))
        return out
    out.append(check("moe_call", "pass", f"one build_moe_ffn call, {len(post_args)} args bound to the "
                     f"{len(names)}-parameter declaration", stage))
    bound = dict(zip(names, post_args))
    wrong = []
    for param, tensor in SCALES.items():
        want = f"model.layers[il].{tensor}"
        got = bound.get(param, "<default nullptr>")
        # the member expression itself, spelled exactly (whitespace aside): an alias would be new code outside
        # the call, which edits_confined_to_call rejects
        if re.sub(r"\s+", "", got) != want:
            hint = ""
            for other, t in SCALES.items():
                if other != param and got.endswith("." + t):
                    hint = (f" ({t} belongs to {other}: that scale is applied to two projections and "
                            f"{param.split('_')[0]}'s own scale never)")
            if got in ("nullptr", "NULL", "<default nullptr>"):
                hint = f" (the {param.split('_')[0]} projection stays unscaled)"
            wrong.append(f"{param} = {got}, expected {want}{hint}")
    out.append(check("scale_args", "fail" if wrong else "pass", wrong or
                     {p: bound[p] for p in SCALES}, stage))
    pre_bound = dict(zip(resolve(decls, pre_args) or names, pre_args))
    moved = [f"{p}: {pre_bound.get(p)} -> {bound.get(p)}" for p in names
             if p not in SCALES and pre_bound.get(p) != bound.get(p)]
    if len(pre_args) != len(post_args):
        moved.insert(0, f"argument count {len(pre_args)} -> {len(post_args)}")
    out.append(check("call_otherwise_unchanged", "fail" if moved else "pass",
                     moved or "every other argument of the call is as in HEAD", stage))
    outside_pre = strip_comments(pre_text[:p0] + pre_text[p1:])
    outside_post = strip_comments(post_text[:q0] + post_text[q1:])
    norm = lambda s: re.sub(r"\s+", " ", s).strip()  # noqa: E731
    out.append(check("edits_confined_to_call", "pass" if norm(outside_pre) == norm(outside_post) else "fail",
                     "no code outside the build_moe_ffn call changed" if norm(outside_pre) == norm(outside_post)
                     else "code outside the build_moe_ffn call changed (new work in the graph)", stage))
    return out
