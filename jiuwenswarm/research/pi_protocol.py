"""Bounded, deterministic protocol and independent reference tools for Pi builds."""
from __future__ import annotations

import ast
import hashlib
import io
import json
import math
import re
import stat
import zipfile
from decimal import Decimal, localcontext
from pathlib import Path
from typing import Mapping

from .checks.research import BUNDLE_FILES, CheckError, _python_check
from .environment import parse_requirements

MAX_DIGITS = 100_000
_DECIMAL_RE = re.compile(r"3\.[0-9]*\Z", re.ASCII)


def _strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate JSON member")
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite JSON")))


def _digits(value):
    if type(value) is not int or not 0 <= value <= MAX_DIGITS:
        raise ValueError("digits must be an integer from 0 to 100000")
    return value


def validate_pi_request(raw_or_record) -> int:
    """Validate a raw request object or its canonical JSON representation."""
    if isinstance(raw_or_record, (str, bytes, bytearray)):
        try:
            raw_or_record = _strict_json(raw_or_record)
        except (ValueError, UnicodeDecodeError, TypeError) as exc:
            raise ValueError("invalid request JSON") from exc
    if not isinstance(raw_or_record, dict) or set(raw_or_record) != {"schema", "digits"}:
        raise ValueError("request must contain exactly schema and digits")
    if raw_or_record["schema"] != "ai4r-pi-cases:1":
        raise ValueError("unsupported request schema")
    return _digits(raw_or_record["digits"])


def _decimal_text(value: str, digits: int) -> str:
    if not isinstance(value, str) or not value.isascii() or _DECIMAL_RE.fullmatch(value) is None:
        raise ValueError("decimal must use ASCII digits and a 3. prefix")
    if len(value) != digits + 2:
        raise ValueError("decimal has incorrect length")
    return value


def parse_pi_output(raw, expected_digits, reference_prefix=None) -> dict:
    expected_digits = _digits(expected_digits)
    try:
        obj = _strict_json(raw)
    except (ValueError, TypeError, UnicodeDecodeError) as exc:
        raise ValueError("invalid output JSON") from exc
    if not isinstance(obj, dict) or set(obj) != {"digits", "decimal"}:
        raise ValueError("output must contain exactly digits and decimal")
    if type(obj["digits"]) is not int or obj["digits"] != expected_digits:
        raise ValueError("output digits mismatch")
    decimal = _decimal_text(obj["decimal"], expected_digits)
    if reference_prefix is not None:
        if not isinstance(reference_prefix, str) or not reference_prefix.isascii() or not reference_prefix.startswith("3."):
            raise ValueError("invalid reference prefix")
        if len(reference_prefix) < expected_digits + 2 or decimal != reference_prefix[: expected_digits + 2]:
            raise ValueError("output differs from reference")
    return {"digits": expected_digits, "decimal": decimal}


def _gauss_legendre(digits: int) -> str:
    """Compute Pi using Decimal Gauss-Legendre with guarded precision."""
    precision = digits + 16
    with localcontext() as ctx:
        ctx.prec = precision
        one = Decimal(1)
        a, b = one, one / Decimal(2).sqrt()
        t, p = Decimal(1) / 4, one
        for _ in range(math.ceil(math.log2(max(1, digits))) + 2):
            an = (a + b) / 2
            b = (a * b).sqrt()
            t -= p * (a - an) * (a - an)
            a, p = an, p * 2
        pi = (a + b) * (a + b) / (4 * t)
        rendered = format(pi, "f")
        whole, _, fractional = rendered.partition(".")
        return whole + "." + fractional[:digits]


def _chudnovsky_bs(digits: int) -> str:
    """Compute Pi via integer Chudnovsky binary splitting, independent of Decimal iteration."""
    terms = digits // 14 + 2

    def split(a, b):
        if b - a == 1:
            if a == 0:
                return 1, 1, 13591409
            p = (6*a-5)*(2*a-1)*(6*a-1)
            q = a*a*a * 10939058860032000
            t = p * (13591409 + 545140134*a)
            if a & 1:
                t = -t
            return p, q, t
        m = (a + b) // 2
        p1, q1, t1 = split(a, m)
        p2, q2, t2 = split(m, b)
        return p1*p2, q1*q2, t1*q2+p1*t2

    p, q, t = split(0, terms)
    scale = 10 ** (digits + 10)
    # Retain `digits` places from a sqrt rounded down at ten guard places.
    numerator = 426880 * math.isqrt(10005 * scale * scale) * q
    scaled = numerator // (t * 10**10)
    whole, frac = divmod(scaled, 10 ** digits)
    # Chunk conversion avoids Python's defensive 4300 decimal-digit int cap.
    chunks = []
    while frac:
        frac, chunk = divmod(frac, 1_000_000_000)
        chunks.append(chunk)
    ordered = list(reversed(chunks))
    frac_text = (str(ordered[0]) + "".join(f"{chunk:09d}" for chunk in ordered[1:])) if ordered else ""
    frac_text = frac_text.rjust(digits, "0")
    return f"{whole}.{frac_text}"


def create_reference(max_digits=MAX_DIGITS) -> dict:
    max_digits = _digits(max_digits)
    first, second = _gauss_legendre(max_digits), _chudnovsky_bs(max_digits)
    if first != second:
        raise ArithmeticError("independent Pi implementations disagree")
    module_source = Path(__file__).read_bytes()
    encoded = first.encode("ascii")
    return {"digits": max_digits, "decimal": first,
            "source_sha256": hashlib.sha256(module_source).hexdigest(),
            "reference_sha256": hashlib.sha256(encoded).hexdigest(),
            "methods": ["decimal-gauss-legendre", "integer-chudnovsky-binary-splitting"]}


def baseline_pi(digits):
    return _gauss_legendre(_digits(digits))


def inspect_pi_bundle(bundle: bytes, pins: Mapping[str, str]) -> dict:
    if len(bundle) > 1024 * 1024:
        raise CheckError("archive_size")
    try:
        with zipfile.ZipFile(io.BytesIO(bundle)) as archive:
            entries = archive.infolist()
            if len(entries) != 3 or {e.filename for e in entries} != BUNDLE_FILES:
                raise CheckError("archive_members")
            if any(e.flag_bits & 1 or stat.S_ISLNK(e.external_attr >> 16) or e.is_dir() for e in entries):
                raise CheckError("archive_members")
            if sum(e.file_size for e in entries) > 1024 * 1024:
                raise CheckError("archive_size")
            files = {e.filename: archive.read(e) for e in entries}
    except (zipfile.BadZipFile, RuntimeError) as exc:
        raise CheckError("archive_valid") from exc
    deps = parse_requirements(files["requirements.txt"])
    if len(deps) > 50 or any(pins.get(k) != v for k, v in deps.items()):
        raise CheckError("dependencies_match_lock")
    checks = [{"path": "requirements.txt", "sha256": hashlib.sha256(files["requirements.txt"]).hexdigest(),
               "syntax_result": "not_applicable", "syntax_detail": None, "forbidden_imports": []}]
    for name in ("poc_patch.py", "run_benchmark.py"):
        tree, check = _python_check(name, files[name])
        checks.append(check)
        if name == "poc_patch.py":
            functions = [node for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                         and node.name == "approximate_pi"]
            if len(functions) != 1 or not functions[0].args.args or functions[0].args.args[0].arg != "digits":
                raise CheckError("pi_algorithm_entrypoint")
            body = [node for node in functions[0].body if not isinstance(node, ast.Expr) or not isinstance(node.value, ast.Constant)]
            if not body or all(isinstance(node, ast.Return) and isinstance(node.value, ast.Constant) for node in body):
                raise CheckError("pi_algorithm_substantive")
            for node in ast.walk(tree):
                if isinstance(node, ast.Constant):
                    if isinstance(node.value, int) and node.value.bit_length() > 3322:
                        raise CheckError("embedded_pi_answer")
                    if isinstance(node.value, str) and len(node.value) > 1000 and re.fullmatch(r"3\.[0-9]+", node.value, re.ASCII):
                        raise CheckError("embedded_pi_answer")
        if name == "run_benchmark.py":
            prints = [n for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "print"]
            valid = [n for n in prints if len(n.args) == 1 and not n.keywords and isinstance(n.args[0], ast.Call)
                     and isinstance(n.args[0].func, ast.Attribute) and isinstance(n.args[0].func.value, ast.Name)
                     and n.args[0].func.value.id == "json" and n.args[0].func.attr == "dumps" and len(n.args[0].args) == 1]
            output_dict = next((n.args[0].args[0] for n in valid if isinstance(n.args[0].args[0], ast.Dict)), None)
            keys = {k.value for k in output_dict.keys if isinstance(k, ast.Constant)} if output_dict else set()
            if len(prints) != 1 or len(valid) != 1 or keys != {"digits", "decimal"}:
                raise CheckError("output_log_format")
    return {"file_checks": checks, "files": files,
            "dependencies": [{"name": k, "version": v} for k, v in deps.items()]}


def run_harness(source_dir, data_path="/resources/validation/data.json") -> str:
    """Run the immutable baseline against the single public benchmark request."""
    request = json.loads(Path(data_path).read_text(encoding="utf-8"))
    digits = validate_pi_request(request)
    result = {"digits": digits, "decimal": baseline_pi(digits)}
    return json.dumps(result, separators=(",", ":"), ensure_ascii=True)
