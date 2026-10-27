"""Offline integrity checks with structured, deterministic evidence.

Unknown/malformed inputs return ``ok=None, cause_class='not_assessable'``.
Successful and failed assessments retain the check's cause class. No inputs are
mutated. Only pin_matches reads local files; it never resolves remote resources.
"""

from collections import Counter
from collections.abc import Mapping
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import re


def _result(ok, cause, evidence):
    return {"ok": ok, "cause_class": cause, "evidence": evidence}


def _unknown(reason):
    return _result(None, "not_assessable", [{"reason": reason}])


def _number(value):
    if isinstance(value, bool):
        raise ValueError("boolean is not a measurement")
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("nonfinite measurement")
    return Fraction(str(value))


def _canonical(value):
    """Preserve types, except equivalent finite integers/floats are equal."""
    if value is None or isinstance(value, (str, bool)):
        return (type(value).__name__, value)
    if isinstance(value, (int, float, Fraction)):
        return ("number", _number(value))
    if isinstance(value, Mapping):
        if not all(isinstance(key, str) for key in value):
            raise ValueError("mapping keys must be strings")
        return ("mapping", tuple(sorted((key, _canonical(item)) for key, item in value.items())))
    if isinstance(value, (list, tuple)):
        return ("sequence", tuple(_canonical(item) for item in value))
    raise ValueError("unsupported value type")


def split_disjoint(train_rows, test_rows, feature_keys=None):
    """Compare mapping rows, independent of row/key ordering.

    By default ignore case-insensitive id/ids and *_id/*_ids columns. Explicit
    feature_keys select the exact feature schema (including IDs if requested).
    Missing selected features or no remaining features cannot be assessed.
    Empty or absent splits cannot establish disjointness.
    """
    if train_rows is None or test_rows is None:
        return _unknown("both splits are required")
    try:
        train, test = list(train_rows), list(test_rows)
        keys = None if feature_keys is None else tuple(feature_keys)
        if not train or not test or keys == () or isinstance(feature_keys, str):
            return _unknown("nonempty splits and feature selection are required")

        def canonical_row(row):
            if not isinstance(row, Mapping) or not all(isinstance(k, str) for k in row):
                raise ValueError("rows must be mappings with string keys")
            selected = keys if keys is not None else tuple(
                k for k in row if k.lower() not in {"id", "ids"}
                and not k.lower().endswith(("_id", "_ids"))
            )
            if not selected:
                raise ValueError("no features remain after ID exclusion")
            return _canonical({k: row[k] for k in selected})

        train_index = {}
        for index, row in enumerate(train):
            train_index.setdefault(canonical_row(row), index)
        overlaps = [
            {"train_index": train_index[key], "test_index": index}
            for index, row in enumerate(test)
            if (key := canonical_row(row)) in train_index
        ]
    except (TypeError, ValueError, KeyError) as exc:
        return _unknown(str(exc))
    return _result(not overlaps, "split_overlap", overlaps)


def pin_matches(path_or_bytes, pinned_sha256):
    """Hash bytes (including empty bytes) or a readable local filesystem path."""
    if path_or_bytes is None or not pinned_sha256:
        return _unknown("content/path and SHA-256 pin are required")
    if not isinstance(pinned_sha256, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", pinned_sha256):
        return _unknown("pin must be a 64-character hexadecimal SHA-256")
    try:
        digest = hashlib.sha256()
        if isinstance(path_or_bytes, (bytes, bytearray, memoryview)):
            digest.update(path_or_bytes)
        else:
            with Path(path_or_bytes).open("rb") as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(block)
    except (OSError, TypeError, ValueError) as exc:
        return _unknown(str(exc))
    actual = digest.hexdigest()
    return _result(actual == pinned_sha256.lower(), "pin_mismatch", [
        {"expected_sha256": pinned_sha256.lower(), "actual_sha256": actual}
    ])


def _sha256_hex(value):
    return isinstance(value, str) and re.fullmatch(r"[0-9a-fA-F]{64}", value) is not None


def snapshot_matches(snapshot, pin, files_by_path):
    """Verify a captured resource snapshot record, then each of its files.

    ``pin`` is the snapshot's reference ({"id", "sha256"}) or its bare SHA-256.
    The pinned digest is that of the canonical record bytes, the same bytes
    the product's store captures (state.json_bytes), not of any file. Each
    ``snapshot["files"]`` entry then pins its content by
    ``artifact_ref["sha256"]``; ``files_by_path`` maps path -> bytes. A listed
    file that is not supplied cannot be assessed. A supplied file the snapshot
    does not list is a mismatch, as is any differing digest.
    """
    if snapshot is None or not pin or files_by_path is None:
        return _unknown("snapshot, pin and file bytes are required")
    try:
        from ..contracts import ResearchError
        from ..state import json_bytes
        digest = pin.get("sha256") if isinstance(pin, Mapping) else pin
        if not _sha256_hex(digest):
            return _unknown("pin must be a reference with, or be, a 64-character hexadecimal SHA-256")
        if not isinstance(snapshot, Mapping) or not isinstance(snapshot.get("files"), list):
            return _unknown("snapshot must be a record with a files list")
        if not isinstance(files_by_path, Mapping):
            return _unknown("files_by_path must map path to bytes")
        listed = {}
        for entry in snapshot["files"]:
            ref = entry.get("artifact_ref") if isinstance(entry, Mapping) else None
            path = entry.get("path") if isinstance(entry, Mapping) else None
            if (not isinstance(path, str) or not isinstance(ref, Mapping) or not _sha256_hex(ref.get("sha256"))
                    or path in listed):
                return _unknown("each snapshot file needs a unique path and artifact_ref sha256")
            listed[path] = ref["sha256"].lower()
        absent = sorted(path for path in listed if path not in files_by_path)
        if absent:
            return _unknown("file bytes not supplied for: " + ", ".join(absent))
        if not all(isinstance(value, (bytes, bytearray, memoryview)) for value in files_by_path.values()):
            return _unknown("file contents must be bytes")
        actual_record = hashlib.sha256(json_bytes(dict(snapshot))).hexdigest()
    except (TypeError, ValueError, AttributeError, ResearchError) as exc:
        return _unknown(str(exc))
    evidence = []
    if actual_record != digest.lower():
        evidence.append({"level": "snapshot_record", "expected_sha256": digest.lower(), "actual_sha256": actual_record})
    for path in sorted(files_by_path):
        actual = hashlib.sha256(bytes(files_by_path[path])).hexdigest()
        if path not in listed:
            evidence.append({"level": "file", "path": path, "reason": "file is not listed in the snapshot",
                             "actual_sha256": actual})
        elif actual != listed[path]:
            evidence.append({"level": "file", "path": path, "expected_sha256": listed[path], "actual_sha256": actual})
    return _result(not evidence, "pin_mismatch", evidence)


def baseline_consistent(declared_definition, replayed_predictions, labels):
    """Validate a constant prediction baseline against its reference labels.

    majority_class/minority_class use observed class counts in labels. Ties are
    ambiguous, so the bare names abstain on a tie. ``majority_class:tie=lowest``
    or ``:tie=highest`` (also for minority_class) names the tie-break: among the
    tied labels, the lowest or highest by value order (numbers numerically,
    strings lexicographically, False before True). Tied labels of different
    types, or of no value order, still abstain. constant:<label> accepts a JSON
    scalar or unquoted text. Labels must be the baseline's fitting population,
    supplied by the caller; predictions may cover a different-sized replay
    population.
    """
    if not declared_definition or replayed_predictions is None or labels is None:
        return _unknown("definition, predictions and reference labels are required")
    try:
        predictions, reference = list(replayed_predictions), list(labels)
        if not predictions or not reference or not isinstance(declared_definition, str):
            return _unknown("nonempty predictions and reference labels are required")
        definition = declared_definition.strip()
        name, _, option = definition.partition(":")
        tie = None
        if name in {"majority_class", "minority_class"} and option:
            if option.replace(" ", "") not in {"tie=lowest", "tie=highest"}:
                return _unknown("unsupported baseline definition")
            tie, definition = option.replace(" ", "")[4:], name
        if definition in {"majority_class", "minority_class"}:
            counts = Counter(_canonical(label) for label in reference)
            extreme = (max if definition == "majority_class" else min)(counts.values())
            candidates = [label for label, count in counts.items() if count == extreme]
            if len(candidates) != 1 and tie is None:
                return _unknown("class count tie requires an explicit tie-break rule")
            if len(candidates) != 1:
                kinds = {label[0] for label in candidates}
                if len(kinds) != 1 or kinds - {"number", "str", "bool"}:
                    return _unknown("tied labels have no common value order")
                candidates.sort(key=lambda label: label[1])
                candidates = candidates[:1] if tie == "lowest" else candidates[-1:]
            expected = candidates[0]
        elif definition.startswith("constant:"):
            literal = definition.partition(":")[2].strip()
            if not literal:
                return _unknown("constant label is absent")
            try:
                label = json.loads(literal)
            except json.JSONDecodeError:
                label = literal
            if isinstance(label, (dict, list)):
                return _unknown("constant label must be scalar")
            expected = _canonical(label)
        else:
            return _unknown("unsupported baseline definition")
        mismatches = [{"prediction_index": index, "actual": prediction}
                      for index, prediction in enumerate(predictions)
                      if _canonical(prediction) != expected]
    except (TypeError, ValueError) as exc:
        return _unknown(str(exc))
    return _result(not mismatches, "baseline_definition_conflict", mismatches)


def units_consistent(metrics):
    """Check same-name unit agreement and fraction [0,1]/percent [0,100].

    Percent values are percentage points: both 95 and 0.95 are valid percentages;
    their magnitude alone cannot establish an incorrectly declared unit.
    """
    if metrics is None:
        return _unknown("metrics are required")
    aliases = {"%": "percent", "percentage": "percent", "percent": "percent",
               "fraction": "fraction", "ratio": "fraction"}
    seen, evidence = {}, []
    try:
        rows = list(metrics)
        if not rows:
            return _unknown("metrics are empty")
        for index, metric in enumerate(rows):
            name, unit = metric["name"], metric["unit"]
            if not isinstance(name, str) or not name.strip() or not isinstance(unit, str) or not unit.strip():
                return _unknown("each metric needs a name and unit")
            unit = aliases.get(unit.strip().lower(), unit.strip().lower())
            value = _number(metric["value"])
            if name in seen and seen[name] != unit:
                evidence.append({"index": index, "name": name, "units": [seen[name], unit]})
            seen.setdefault(name, unit)
            upper = {"fraction": 1, "percent": 100}.get(unit)
            if upper is not None and not 0 <= value <= upper:
                evidence.append({"index": index, "name": name, "value": str(value),
                                 "unit": unit, "allowed_range": [0, upper]})
    except (KeyError, TypeError, ValueError, ZeroDivisionError) as exc:
        return _unknown(str(exc))
    return _result(not evidence, "unit_conflict", evidence)


def no_stale_duplicate(manifest_entries):
    """Check manifest roles and explicitly marked obsolete references.

    Entries require path, sha256, role and version. referenced defaults to True;
    False marks retained history. supersedes is a path/hash or a list of them,
    linking a replacement to older entries (transitive chains are supported).
    Lower version numbers alone do not imply obsolescence. Obsolete markers are
    standalone old/stale/obsolete/deprecated/archived/backup tokens in the basename
    or version. A supersedes link resolves divergent-role hashes, but cannot make
    an explicitly obsolete file safe to reference.
    """
    if manifest_entries is None:
        return _unknown("manifest is required")
    try:
        entries = list(manifest_entries)
        if not entries:
            return _unknown("manifest is empty")
        links, evidence = {}, []
        for index, entry in enumerate(entries):
            for field in ("path", "sha256", "role", "version"):
                if field not in entry or entry[field] is None or str(entry[field]).strip() == "":
                    return _unknown("each entry requires path, sha256, role and version")
            if not all(isinstance(entry[field], str) for field in ("path", "sha256", "role")):
                return _unknown("path, sha256 and role must be strings")
            if not re.fullmatch(r"[0-9a-fA-F]{64}", entry["sha256"]):
                return _unknown("manifest SHA-256 must be hexadecimal")
            if not isinstance(entry.get("referenced", True), bool):
                return _unknown("referenced must be boolean")
            supersedes = entry.get("supersedes", [])
            supersedes = [supersedes] if isinstance(supersedes, str) else list(supersedes)
            if not all(isinstance(link, str) for link in supersedes):
                return _unknown("supersedes must contain paths or hashes")
            links[index] = supersedes
            basename = PurePosixPath(entry["path"].replace("\\", "/")).name
            tokens = set(re.split(r"[^a-z0-9]+", (basename + " " + str(entry["version"])).lower()))
            if entry.get("referenced", True) and tokens & {"old", "stale", "obsolete", "deprecated", "archived", "backup"}:
                evidence.append({"path": entry["path"], "reason": "obsolete file remains referenced"})

        def supersedes(new, old, visited=None):
            visited = set() if visited is None else visited
            if new in visited:
                return False
            visited.add(new)
            for candidate, entry in enumerate(entries):
                if candidate == new or entry["role"] != entries[new]["role"]:
                    continue
                if entry["path"] in links[new] or entry["sha256"].lower() in [s.lower() for s in links[new]]:
                    if candidate == old or supersedes(candidate, old, visited):
                        return True
            return False

        for first, left in enumerate(entries):
            for second in range(first + 1, len(entries)):
                right = entries[second]
                if left["role"] == right["role"] and left["sha256"].lower() != right["sha256"].lower():
                    forward, backward = supersedes(first, second), supersedes(second, first)
                    if forward == backward:
                        evidence.append({"paths": [left["path"], right["path"]], "role": left["role"],
                                         "reason": "divergent hashes lack an unambiguous supersedes chain"})
    except (TypeError, KeyError, ValueError) as exc:
        return _unknown(str(exc))
    return _result(not evidence, "stale_duplicate_dataset", evidence)


def bound_feasible(metric_value_range, target):
    """Test exact target membership in an inclusive (lower, upper) interval.

    Numbers and rational strings (e.g. '1/3') are accepted. Decimal float spelling
    is used instead of binary floating-point arithmetic. The caller supplies
    the metric's range; no metric-specific range or target direction is guessed.
    """
    if metric_value_range is None or target is None:
        return _unknown("metric range and target are required")
    try:
        lower, upper = metric_value_range
        lower, upper, value = _number(lower), _number(upper), _number(target)
        if lower > upper:
            return _unknown("metric range is reversed")
    except (TypeError, ValueError, ZeroDivisionError) as exc:
        return _unknown(str(exc))
    return _result(lower <= value <= upper, "infeasible_bound", [
        {"lower": str(lower), "upper": str(upper), "target": str(value)}
    ])
