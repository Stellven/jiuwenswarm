"""Protected, deterministic M1 scientific arithmetic and C002 evidence handling.

These functions do not execute generated code or decide infrastructure acceptance.
The owning runner admits their check results and the gate persists acceptance.
"""
from __future__ import annotations

import json
import math
import statistics
from decimal import Decimal
from collections.abc import Iterable, Mapping, Sequence
from typing import Any


class ScienceError(ValueError):
    """A source scientific/protocol invariant was violated."""


UNMEASURED_REASONS = frozenset({"run_failed", "timeout", "metric_not_emitted",
                                 "non_finite_value", "resource_limit_exceeded"})
CLASSIFICATIONS = frozenset({"PASS", "FAIL", "INCONCLUSIVE", "CONDITIONALLY_ACCEPTABLE"})


def finite(value: Any) -> bool:
    try:
        return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
    except OverflowError:
        return False


def rule_text(outcome_rule: Mapping, applied: str) -> str:
    """Canonical textual projection of a registered rule; it adds no threshold."""
    if applied == 'unmeasured':
        return 'unmeasured: a registered metric side has no value'
    if applied == 'middle':
        return 'middle: no registered region matched'
    rule = outcome_rule['conditional_rule'] if applied == 'conditional' else outcome_rule[applied]
    comparator = {'lt': '<', 'le': '<=', 'eq': '==', 'ge': '>=', 'gt': '>'}[rule['comparator']]
    number = lambda value: json.dumps(value, allow_nan=False, separators=(',', ':'))
    expression = number(rule['offset']) if rule['reference'] == 'constant' else number(rule['factor']) + ' * baseline + ' + number(rule['offset'])
    return applied + ': treatment ' + comparator + ' ' + expression


def close(left: float, right: float) -> bool:
    return finite(left) and finite(right) and math.isclose(left, right, rel_tol=1e-9, abs_tol=0)


def aggregate(values: Sequence[float], method: str) -> float:
    if not values or not all(finite(x) for x in values):
        raise ScienceError("aggregate requires finite observed values")
    operations = {"min": min, "max": max, "mean": statistics.mean, "median": statistics.median}
    if method not in operations:
        raise ScienceError("unsupported aggregation")
    result = operations[method](values)
    if not finite(result):
        raise ScienceError("nonfinite aggregate")
    return result


def threshold(rule: Mapping[str, Any], baseline: float) -> float:
    if (rule.get("operand") != "treatment" or rule.get("comparator") not in {"lt", "le", "eq", "ge", "gt"}
            or rule.get("reference") not in {"constant", "baseline"}
            or not finite(rule.get("factor")) or not finite(rule.get("offset"))):
        raise ScienceError("invalid ComparisonRule")
    if rule["reference"] == "constant":
        if rule["factor"] != 0:
            raise ScienceError("constant rule factor must be zero")
        result = rule["offset"]
    else:
        if not finite(baseline):
            raise ScienceError("baseline threshold requires a finite baseline")
        # Preserve the decimal contract boundary: .8 + .05 must be .85,
        # not .8500000000000001, when applying an inclusive additive target.
        result = float(Decimal(str(rule['factor'])) * Decimal(str(baseline)) + Decimal(str(rule['offset'])))
    if not finite(result):
        raise ScienceError("nonfinite threshold")
    return result


def rule_holds(rule: Mapping[str, Any], baseline: float, treatment: float) -> bool:
    if not finite(treatment):
        raise ScienceError("rule requires a finite treatment")
    t = threshold(rule, baseline)
    return {"lt": lambda: treatment < t, "le": lambda: treatment <= t,
            "eq": lambda: close(treatment, t), "ge": lambda: treatment >= t,
            "gt": lambda: treatment > t}[rule["comparator"]]()


def _region(rule: Mapping[str, Any], baseline: float) -> tuple[float, bool, float, bool]:
    t = threshold(rule, baseline)
    return {"lt": (-math.inf, False, t, False), "le": (-math.inf, False, t, True),
            "eq": (t, True, t, True), "ge": (t, True, math.inf, False),
            "gt": (t, False, math.inf, False)}[rule["comparator"]]


def _intersects(a: tuple, b: tuple) -> bool:
    low, high = max(a[0], b[0]), min(a[2], b[2])
    if low < high:
        return True
    if low > high:
        return False
    return all((low > r[0] or r[1]) and (low < r[2] or r[3]) for r in (a, b))


def validate_rule_regions(rule: Mapping[str, Any], direction: str) -> None:
    """Use exact constant regions, otherwise the three pinned source probes."""
    families = {"lower_better": ({"lt", "le"}, {"gt", "ge"}),
                "higher_better": ({"gt", "ge"}, {"lt", "le"})}
    if direction not in families:
        raise ScienceError("unknown metric direction")
    success, falsification = rule["success"], rule["falsification"]
    if success.get("comparator") not in families[direction][0] or falsification.get("comparator") not in families[direction][1]:
        raise ScienceError("rule_direction_consistent")
    conditional = rule.get("conditional_rule")
    if rule.get("middle") == "INCONCLUSIVE":
        if conditional is not None or rule.get("conditional_meaning") is not None:
            raise ScienceError("conditional_rule_in_middle")
    elif rule.get("middle") != "CONDITIONALLY_ACCEPTABLE" or not conditional or not rule.get("conditional_meaning"):
        raise ScienceError("conditional_rule_in_middle")
    checks = [success, falsification] + ([conditional] if conditional else [])
    probes = [1] if all(x.get("reference") == "constant" for x in checks) else [.001, 1, 1000]
    for baseline in probes:
        s, f = _region(success, baseline), _region(falsification, baseline)
        if _intersects(s, f):
            raise ScienceError("boundaries_disjoint")
        if conditional and (_intersects(_region(conditional, baseline), s)
                            or _intersects(_region(conditional, baseline), f)):
            raise ScienceError("conditional_rule_in_middle")


def classify_metric(baseline: float | None, treatment: float | None,
                    rule: Mapping[str, Any]) -> tuple[str, str, float | None]:
    if baseline is None or treatment is None:
        return "INCONCLUSIVE", "unmeasured", None
    success = rule_holds(rule["success"], baseline, treatment)
    falsification = rule_holds(rule["falsification"], baseline, treatment)
    if success and falsification:
        raise ScienceError("actual overlapping outcome regions: defective blueprint")
    if success:
        return "PASS", "success", threshold(rule["success"], baseline)
    if falsification:
        return "FAIL", "falsification", threshold(rule["falsification"], baseline)
    conditional = rule.get("conditional_rule")
    if (rule.get("middle") == "CONDITIONALLY_ACCEPTABLE" and conditional
            and rule_holds(conditional, baseline, treatment)):
        return "CONDITIONALLY_ACCEPTABLE", "conditional", threshold(conditional, baseline)
    return "INCONCLUSIVE", "middle", None


def overall_classification(findings: Iterable[str], plausibility: str) -> str:
    findings = list(findings)
    if not findings or not set(findings) <= CLASSIFICATIONS:
        raise ScienceError("invalid findings")
    if plausibility not in {"plausible", "implausible", "not_assessable"}:
        raise ScienceError("invalid plausibility")
    if plausibility == "implausible":
        return "INCONCLUSIVE"
    for value in ["FAIL", "INCONCLUSIVE", "CONDITIONALLY_ACCEPTABLE"]:
        if value in findings:
            return value
    return "PASS"


def _unique_pairs(pairs: list[tuple]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ScienceError("duplicate log key")
        result[key] = value
    return result


def empirical_row(sequence: int, metric_ids: Sequence[str], stdout: bytes | str,
                  exit_code: int, termination_reason: str | None = None) -> dict:
    if type(sequence) is not int or sequence < 1 or not metric_ids or len(set(metric_ids)) != len(metric_ids):
        raise ScienceError("invalid empirical identity")
    observed: dict = {}
    reasons: dict = {}
    terminal = {"timeout": "timeout", "deadline": "timeout", "resource_limit_exceeded": "resource_limit_exceeded",
                "memory_limit": "resource_limit_exceeded", "cpu_limit": "resource_limit_exceeded"}.get(termination_reason)
    if exit_code != 0 or terminal:
        reasons = dict.fromkeys(metric_ids, terminal or "run_failed")
    else:
        if isinstance(stdout, bytes):
            stdout = stdout.decode("utf-8", errors="replace")
        lines = stdout.strip().splitlines()
        if len(lines) > 1:
            raise ScienceError("multiple output log records")
        try:
            parsed = json.loads(stdout, object_pairs_hook=_unique_pairs)
        except (ValueError, TypeError) as exc:
            if isinstance(exc, ScienceError):
                raise
            parsed = None
        values = parsed.get("metrics") if isinstance(parsed, dict) and set(parsed) == {"metrics"} else None
        if isinstance(values, dict) and set(values) - set(metric_ids):
            raise ScienceError("unknown metric ID in output log")
        for metric in metric_ids:
            if not isinstance(values, dict) or metric not in values:
                reasons[metric] = "metric_not_emitted"
            elif not finite(values[metric]):
                reasons[metric] = "non_finite_value"
            else:
                observed[metric] = values[metric]
    return {"sequence": sequence, "status": "measured" if not reasons else "partial" if observed else "unmeasured",
            "metrics": observed, "unmeasured_metrics": reasons}


def validate_empirical(rows: Sequence[Mapping], metric_ids: Sequence[str], receipt_sequences: Sequence[int]) -> None:
    sequences = [row.get("sequence") for row in rows]
    if sequences != list(receipt_sequences) or sequences != list(range(1, len(rows) + 1)):
        raise ScienceError("empirical and actual receipt sequences differ")
    for row in rows:
        metrics, reasons = row.get("metrics"), row.get("unmeasured_metrics")
        if not isinstance(metrics, dict) or not isinstance(reasons, dict):
            raise ScienceError("C002 requires both metric maps")
        if set(metrics) & set(reasons) or set(metrics) | set(reasons) != set(metric_ids):
            raise ScienceError("C002 metric coverage")
        expected = "measured" if not reasons else "partial" if metrics else "unmeasured"
        if row.get("status") != expected or not all(finite(x) for x in metrics.values()) or not set(reasons.values()) <= UNMEASURED_REASONS:
            raise ScienceError("C002 invalid status, value or reason")


def metric_payload(metric: Mapping, baseline: Sequence[float], treatment: Sequence[float], repeat_count: int,
                   baseline_reason: str | None = None, treatment_reason: str | None = None) -> dict:
    def side(values: Sequence[float], reason: str | None) -> dict:
        if len(values) > repeat_count:
            raise ScienceError("extra repeats")
        for value in values:
            if not finite(value) or (metric.get("valid_min") is not None and value < metric["valid_min"]) or (metric.get("valid_max") is not None and value > metric["valid_max"]):
                raise ScienceError("measurement_within_declared_range")
        if len(values) == repeat_count:
            if reason is not None:
                raise ScienceError("complete side cannot carry missing reason")
            value = aggregate(values, metric["aggregation"])
            if (metric.get("valid_min") is not None and value < metric["valid_min"]) or (metric.get("valid_max") is not None and value > metric["valid_max"]):
                raise ScienceError("aggregate outside range")
            return {"repeats": list(values), "value": value, "unmeasured_reason": None}
        if reason not in UNMEASURED_REASONS:
            raise ScienceError("incomplete side requires source reason")
        return {"repeats": list(values), "value": None, "unmeasured_reason": reason}
    b, t = side(baseline, baseline_reason), side(treatment, treatment_reason)
    return {"metric_id": metric["metric_id"], "unit": metric["unit"], "aggregation": metric["aggregation"],
            "baseline": b, "treatment": t,
            "delta": None if b["value"] is None or t["value"] is None else t["value"] - b["value"]}
