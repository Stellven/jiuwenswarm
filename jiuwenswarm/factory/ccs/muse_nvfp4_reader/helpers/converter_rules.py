"""Static gate rules for a Muse NVFP4 reader (converter) change. Standard library only.

Input: the patch text and the post-images of the files it touches (rebuilt by patchlib from the checkout's
HEAD, or from a stock copy in the capsule tests). Output: checks {name, status, stage, detail}.

The rules read the change, never run it. What they cannot decide (for example a gate/up split written in a
shape they do not recognize) is reported `inconclusive`, and the runtime check on the tiny checkpoint decides.
"""
import ast
import re

STAGE = "native CC execution"
ALLOWED = re.compile(r"^conversion/[A-Za-z0-9_]+\.py$")
PROTECTED = ("gguf-py/", "src/", "ggml/", "include/", "common/", "tools/", "convert_hf_to_gguf.py")
PACK_CALLS = {"_nvfp4_pack"}
EAGER_WRITERS = {"_repack_nvfp4", "_flush_nvfp4_experts"}
LAZY_TYPES = {"LazyNumpyTensor", "LazyTorchTensor"}
REDUCTIONS = {"sum", "mean", "prod", "max", "min", "amax"}


def check(name, status, detail, stage=STAGE):
    return {"name": name, "status": status, "stage": stage, "detail": detail}


def call_name(node):
    func = node.func
    if isinstance(func, ast.Attribute):
        return func.attr
    if isinstance(func, ast.Name):
        return func.id
    return None


def source_of(text, node):
    return ast.get_source_segment(text, node) or ""


def find_reader(trees):
    """(path, class, function) of the method that reads stacked experts with their block scales."""
    found = []
    for path, (text, tree) in trees.items():
        for cls in [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]:
            for fn in cls.body:
                if not isinstance(fn, ast.FunctionDef):
                    continue
                body = source_of(text, fn)
                if "gate_up" in body and "weight_scale" in body and any(
                        isinstance(n, ast.Call) and call_name(n) in PACK_CALLS | EAGER_WRITERS for n in ast.walk(fn)):
                    found.append((path, cls, fn))
    return found


def enclosing_deferred(fn):
    """Map id(node) -> True when the node sits inside a nested def or lambda of fn (deferred code)."""
    deferred = {}

    def visit(node, inside):
        for child in ast.iter_child_nodes(node):
            nested = inside or isinstance(child, (ast.FunctionDef, ast.Lambda, ast.AsyncFunctionDef))
            deferred[id(child)] = nested
            visit(child, nested)

    visit(fn, False)
    return deferred


def lazy_rule(text, fn):
    deferred = enclosing_deferred(fn)
    calls = [n for n in ast.walk(fn) if isinstance(n, ast.Call)]
    eager_writes = [call_name(c) for c in calls if call_name(c) in EAGER_WRITERS]
    if eager_writes:
        return "fail", f"calls {sorted(set(eager_writes))} for stacked experts: those write an eager array per call"
    packs = [c for c in calls if call_name(c) in PACK_CALLS]
    eager = [c for c in packs if not deferred.get(id(c))]
    if eager:
        return "fail", (f"_nvfp4_pack runs when the method runs (line {eager[0].lineno}), so every repacked expert "
                        "is held until the final write; defer it inside a function given to a lazy tensor")
    lazy_calls = [c for c in calls if call_name(c) in LAZY_TYPES]
    if not lazy_calls:
        return "fail", "no gguf.LazyNumpyTensor / LazyTorchTensor is built for the repacked experts"
    handed = set()
    for c in lazy_calls:
        for node in ast.walk(c):
            if isinstance(node, ast.Name):
                handed.add(node.id)
            if isinstance(node, ast.Lambda):
                handed.add(id(node))
    holders = []
    for node in ast.walk(fn):
        if isinstance(node, (ast.FunctionDef, ast.Lambda)) and node is not fn:
            if any(isinstance(c, ast.Call) and call_name(c) in PACK_CALLS for c in ast.walk(node)):
                holders.append(node)
    loose = [h for h in holders if (h.name if isinstance(h, ast.FunctionDef) else id(h)) not in handed]
    if loose:
        return "fail", "the function that repacks is not handed to the lazy tensor: " + ", ".join(
            getattr(h, "name", "<lambda>") for h in loose)
    return "pass", f"_nvfp4_pack deferred in {', '.join(getattr(h, 'name', '<lambda>') for h in holders)} and handed to a lazy tensor"


def column_rule(text, fn):
    reductions = []
    for c in ast.walk(fn):
        if isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute) and c.func.attr in REDUCTIONS:
            receiver = source_of(text, c.func.value)
            if re.search(r"scale|s2\b", receiver):
                reductions.append(source_of(text, c))
    if reductions:
        return "fail", f"reduces a scale over its columns ({reductions[0]}): gate and up have separate scale_2 values"
    for node in ast.walk(fn):
        if isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Tuple) and len(node.slice.elts) == 2:
            first, second = node.slice.elts
            if isinstance(first, ast.Slice) and first.lower is None and first.upper is None and not isinstance(second, ast.Slice):
                return "pass", f"per-column selection: {source_of(text, node)}"
    return "fail", "no [:, column] selection found: weight_scale_2 [E, 2] must give gate column 0 and up column 1"


def _is_zero(node):
    return isinstance(node, ast.Constant) and node.value == 0


def _halves(text, node):
    return "// 2" in source_of(text, node) or "//2" in source_of(text, node)


def mapping_rule(text, fn):
    """Recognize (TYPE, row_start, row_end, column) rows naming FFN_GATE_EXP / FFN_UP_EXP; else inconclusive."""
    rows = {}
    for node in ast.walk(fn):
        if isinstance(node, (ast.Tuple, ast.List)):
            elts = node.elts
        elif isinstance(node, ast.Call):
            elts = list(node.args)
        else:
            continue
        kinds = [i for i, e in enumerate(elts) if isinstance(e, ast.Attribute) and e.attr in ("FFN_GATE_EXP", "FFN_UP_EXP")]
        if len(kinds) == 1 and kinds[0] == 0 and len(elts) == 4:
            rows[elts[0].attr] = elts[1:]
    if set(rows) != {"FFN_GATE_EXP", "FFN_UP_EXP"}:
        return "inconclusive", "gate/up split not written as (TYPE, row_start, row_end, column); the runtime check decides"
    problems = []
    g_start, _, g_col = rows["FFN_GATE_EXP"]
    u_start, _, u_col = rows["FFN_UP_EXP"]
    if not _is_zero(g_start):
        problems.append(f"gate starts at row {source_of(text, g_start)}, not 0 (gate is the first half)")
    if not _halves(text, u_start):
        problems.append(f"up starts at row {source_of(text, u_start)}, not the half")
    for label, col, want in (("gate", g_col, 0), ("up", u_col, 1)):
        if isinstance(col, ast.Constant) and isinstance(col.value, int):
            if col.value != want:
                problems.append(f"{label} takes weight_scale_2 column {col.value}, not {want}")
        else:
            return "inconclusive", f"{label} scale column is {source_of(text, col)}; the runtime check decides"
    if problems:
        return "fail", "; ".join(problems)
    return "pass", "gate rows [0, I) with scale_2 column 0, up rows [I, 2I) with column 1"


def literal_rule(text, fn, literal, what):
    for node in ast.walk(fn):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value == literal:
            return "pass", f"writes {literal}"
    return "fail", f"no {literal} tensor is written: {what}"


def static_checks(patch_files, post, stage=STAGE):
    """patch_files: patchlib.parse_patch output; post: {path: post-image text}. Returns checks."""
    out = []
    paths = sorted({p for fp in patch_files for p in (fp["old"], fp["new"]) if p})
    outside = [p for p in paths if not ALLOWED.match(p)]
    out.append(check("allowed_paths", "fail" if outside else "pass",
                     f"outside conversion/*.py: {outside}" if outside else f"touches {paths}", stage))
    protected = [p for p in paths if p.startswith(PROTECTED)]
    out.append(check("protected_paths", "fail" if protected else "pass",
                     f"edits protected files: {protected}" if protected else "no gguf-py, src, ggml or tool edits", stage))
    odd = [fp["new"] or fp["old"] for fp in patch_files if fp["binary"] or fp["mode_change"] or fp["deleted"]]
    out.append(check("plain_text_edits", "fail" if odd else "pass",
                     f"binary, mode, rename or delete: {odd}" if odd else "text edits only", stage))

    trees, broken = {}, []
    for path, text in post.items():
        if not path.endswith(".py"):
            continue
        try:
            trees[path] = (text, ast.parse(text, filename=path))
        except SyntaxError as exc:
            broken.append(f"{path}:{exc.lineno}: {exc.msg}")
    out.append(check("python_parses", "fail" if broken else "pass", broken or sorted(trees), stage))

    readers = find_reader({p: t for p, t in trees.items() if ALLOWED.match(p)})
    if not readers:
        out.append(check("stacked_reader", "fail", "no method in conversion/ reads stacked gate_up/down experts "
                         "with their weight_scale and repacks them with the stock NVFP4 packer", stage))
        for name in ("reuses_stock_pack", "lazy_repack", "separate_gate_up_scales", "gate_up_mapping",
                     "scale_tensors_written", "input_scale_written", "no_requantize"):
            out.append(check(name, "fail", "no stacked expert reader to inspect", stage))
        return out
    path, cls, fn = readers[0]
    text = trees[path][0]
    out.append(check("stacked_reader", "pass", f"{path}: {cls.name}.{fn.name} (line {fn.lineno})", stage))
    names = {call_name(c) for c in ast.walk(fn) if isinstance(c, ast.Call)}
    out.append(check("reuses_stock_pack", "pass" if names & PACK_CALLS else "fail",
                     "calls the stock _nvfp4_pack" if names & PACK_CALLS
                     else "does not call the stock _nvfp4_pack (blocks must move bit for bit, not be re-derived)", stage))
    requant = sorted(n for n in names if n and n.endswith("quantize"))
    out.append(check("no_requantize", "fail" if requant else "pass",
                     f"calls {requant}: NVFP4 blocks must not be dequantized or requantized" if requant
                     else "no quantize/dequantize call", stage))
    out.append(check("lazy_repack", *lazy_rule(text, fn), stage=stage))
    out.append(check("separate_gate_up_scales", *column_rule(text, fn), stage=stage))
    out.append(check("gate_up_mapping", *mapping_rule(text, fn), stage=stage))
    out.append(check("scale_tensors_written", *literal_rule(text, fn, ".scale", "the [n_expert] weight_scale_2 is lost"), stage=stage))
    out.append(check("input_scale_written", *literal_rule(text, fn, ".input_scale", "the input_scale planes are dropped"), stage=stage))
    chained = fn.name != "_generate_nvfp4_tensors" or any(
        isinstance(c, ast.Call) and call_name(c) == "_generate_nvfp4_tensors" for c in ast.walk(fn))
    out.append(check("stock_hook_chained", "pass" if chained else "inconclusive",
                     "calls the stock _generate_nvfp4_tensors for every other NVFP4 tensor" if chained
                     else "the override does not chain to super()._generate_nvfp4_tensors(); per-expert and dense NVFP4 tensors would be left unhandled", stage))
    return out
