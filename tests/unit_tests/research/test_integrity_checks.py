"""Offline contract and boundary coverage for general integrity checks."""

from copy import deepcopy
from fractions import Fraction
import hashlib
from pathlib import Path
import tempfile
import unittest

from jiuwenswarm.research.checks.integrity import (
    baseline_consistent,
    bound_feasible,
    no_stale_duplicate,
    pin_matches,
    snapshot_matches,
    split_disjoint,
    units_consistent,
)


class IntegrityChecksTest(unittest.TestCase):
    def assert_result(self, result, ok, cause):
        self.assertEqual(set(result), {"ok", "cause_class", "evidence"})
        self.assertIs(result["ok"], ok)
        self.assertEqual(result["cause_class"], cause)
        self.assertIsInstance(result["evidence"], list)
        if ok is False or ok is None:
            self.assertTrue(result["evidence"])

    def assert_unknown(self, result):
        self.assert_result(result, None, "not_assessable")

    def test_split_disjoint(self):
        self.assert_result(split_disjoint([{"x": 1}], [{"x": 2}]), True, "split_overlap")

    def test_split_ignores_ids_and_row_and_key_order(self):
        train = [{"id": "a", "x": 1, "nested": {"a": 2, "b": [3]}}, {"x": 8}]
        test = [{"x": 9}, {"nested": {"b": [3.0], "a": 2.0}, "x": 1.0, "id": "b"}]
        original = deepcopy((train, test))
        result = split_disjoint(train, test)
        self.assert_result(result, False, "split_overlap")
        self.assertEqual(result["evidence"], [{"train_index": 0, "test_index": 1}])
        self.assertEqual((train, test), original)

    def test_split_id_columns_and_explicit_features(self):
        train = [{"sample_id": 1, "x": 0.5, "label": "a"}]
        test = [{"sample_id": 2, "x": 0.5, "label": "b"}]
        self.assert_result(split_disjoint(train, test, ["x"]), False, "split_overlap")
        self.assert_result(split_disjoint(train, test, ["sample_id", "x"]), True, "split_overlap")
        self.assert_result(split_disjoint([{"ID": 1, "x": 3}], [{"ID": 2, "x": 3}]), False, "split_overlap")

    def test_split_preserves_type_and_exact_value(self):
        for other in (True, "1", 1.0000000000000002):
            with self.subTest(other=other):
                self.assert_result(split_disjoint([{"x": 1}], [{"x": other}]), True, "split_overlap")

    def test_split_not_assessable(self):
        for args in ((None, []), ([], []), ([{"id": 1}], [{"id": 2}]),
                     ([{"x": 1}], [{"y": 1}], ["x"]), ([{"x": float("nan")}], [{"x": 1}])):
            with self.subTest(args=args):
                self.assert_unknown(split_disjoint(*args))

    def test_pin_bytes_and_empty_bytes(self):
        for content in (b"", b"dataset\x00\xff"):
            pin = hashlib.sha256(content).hexdigest()
            self.assert_result(pin_matches(content, pin.upper()), True, "pin_mismatch")
            self.assert_result(pin_matches(content + b"changed", pin), False, "pin_mismatch")

    def test_pin_local_file(self):
        with tempfile.NamedTemporaryFile(dir=Path(__file__).parent, delete=False) as stream:
            stream.write(b"local data")
            path = Path(stream.name)
        try:
            pin = hashlib.sha256(path.read_bytes()).hexdigest()
            self.assert_result(pin_matches(path, pin), True, "pin_mismatch")
            self.assert_result(pin_matches(str(path), "0" * 64), False, "pin_mismatch")
            self.assert_unknown(pin_matches(path.with_name("missing.bin"), pin))
        finally:
            path.unlink()

    def test_pin_not_assessable(self):
        for source, pin in ((None, "0" * 64), (b"", None), (b"data", "invalid")):
            self.assert_unknown(pin_matches(source, pin))

    def test_baseline_majority_and_minority(self):
        labels = ["a", "a", "b"]
        for definition, expected, wrong in (("majority_class", "a", "b"), ("minority_class", "b", "a")):
            with self.subTest(definition=definition):
                self.assert_result(baseline_consistent(definition, [expected] * 5, labels), True,
                                   "baseline_definition_conflict")
                result = baseline_consistent(definition, [expected, wrong], labels)
                self.assert_result(result, False, "baseline_definition_conflict")
                self.assertEqual(result["evidence"][0]["prediction_index"], 1)

    def test_baseline_constants(self):
        for declaration, expected, wrong in (("constant:cat", "cat", "dog"),
                                              ('constant:"1"', "1", 1), ("constant:1", 1.0, 2),
                                              ("constant:false", False, 0)):
            with self.subTest(declaration=declaration):
                self.assert_result(baseline_consistent(declaration, [expected], [0]), True,
                                   "baseline_definition_conflict")
                self.assert_result(baseline_consistent(declaration, [wrong], [0]), False,
                                   "baseline_definition_conflict")

    def test_baseline_equivalent_numeric_labels(self):
        self.assert_result(baseline_consistent("majority_class", [1.0], [1, 1.0, 2]), True,
                           "baseline_definition_conflict")

    def test_baseline_not_assessable(self):
        for args in ((None, [1], [1]), ("majority_class", None, [1]),
                     ("majority_class", [1], None), ("majority_class", [], [1]),
                     ("majority_class", [1], []), ("majority_class", [1], [1, 2]),
                     ("minority_class", [1], [1, 2]), ("unknown", [1], [1]),
                     ("constant:", [1], [1])):
            with self.subTest(args=args):
                self.assert_unknown(baseline_consistent(*args))

    def test_units_fraction_and_percent(self):
        metrics = [{"name": "accuracy", "value": 0.95, "unit": "fraction"},
                   {"name": "accuracy", "value": 1, "unit": "ratio"},
                   {"name": "recall", "value": 95, "unit": "%"},
                   {"name": "recall", "value": 0.95, "unit": "percent"}]
        original = deepcopy(metrics)
        self.assert_result(units_consistent(metrics), True, "unit_conflict")
        self.assertEqual(metrics, original)

    def test_units_conflicting_same_name(self):
        self.assert_result(units_consistent([
            {"name": "accuracy", "value": 0.95, "unit": "fraction"},
            {"name": "accuracy", "value": 95, "unit": "percent"},
        ]), False, "unit_conflict")
        self.assert_result(units_consistent([
            {"name": "time", "value": 1, "unit": "seconds"},
            {"name": "time", "value": 1, "unit": "milliseconds"},
        ]), False, "unit_conflict")

    def test_units_outside_declared_range(self):
        for unit, value in (("fraction", 95), ("fraction", 1.01), ("fraction", -0.1),
                            ("percent", 101), ("percent", -1)):
            with self.subTest(unit=unit, value=value):
                self.assert_result(units_consistent([{"name": "score", "value": value, "unit": unit}]),
                                   False, "unit_conflict")

    def test_units_not_assessable(self):
        for metrics in (None, [], [{}], [{"name": "a", "value": None, "unit": "fraction"}],
                        [{"name": "a", "value": float("inf"), "unit": "fraction"}]):
            self.assert_unknown(units_consistent(metrics))

    @staticmethod
    def entry(path="data.csv", content=b"data", role="training", version="v1", **extra):
        return {"path": path, "sha256": hashlib.sha256(content).hexdigest(),
                "role": role, "version": version, **extra}

    def test_manifest_same_hash_or_distinct_role(self):
        self.assert_result(no_stale_duplicate([self.entry(), self.entry("copy.csv")]), True,
                           "stale_duplicate_dataset")
        self.assert_result(no_stale_duplicate([self.entry(), self.entry("test.csv", b"test", "test")]),
                           True, "stale_duplicate_dataset")

    def test_manifest_divergent_hashes(self):
        self.assert_result(no_stale_duplicate([self.entry(), self.entry("next.csv", b"changed", version="v2")]),
                           False, "stale_duplicate_dataset")

    def test_manifest_supersedes_path_hash_and_chain(self):
        first = self.entry()
        second = self.entry("v2.csv", b"two", version="v2", supersedes=first["path"])
        third = self.entry("v3.csv", b"three", version="v3", supersedes=[second["sha256"]])
        entries = [third, first, second]
        original = deepcopy(entries)
        self.assert_result(no_stale_duplicate(entries), True, "stale_duplicate_dataset")
        self.assertEqual(entries, original)

    def test_manifest_missing_link_and_cycles(self):
        for link in ("nonexistent.csv", "next.csv"):
            first = self.entry(supersedes=link)
            second = self.entry("next.csv", b"two", supersedes="data.csv" if link == "next.csv" else [])
            self.assert_result(no_stale_duplicate([first, second]), False, "stale_duplicate_dataset")

    def test_manifest_obsolete_reference(self):
        for entry in (self.entry("dataset.old.csv"), self.entry(version="deprecated"),
                      self.entry(r"C:\data\dataset_backup.csv")):
            with self.subTest(entry=entry):
                self.assert_result(no_stale_duplicate([entry]), False, "stale_duplicate_dataset")
                self.assert_result(no_stale_duplicate([dict(entry, referenced=False)]), True,
                                   "stale_duplicate_dataset")
        self.assert_result(no_stale_duplicate([self.entry("household.csv")]), True,
                           "stale_duplicate_dataset")

    def test_manifest_supersedes_does_not_hide_stale_reference(self):
        first = self.entry("data_old.csv")
        second = self.entry("current.csv", b"two", supersedes=first["path"])
        self.assert_result(no_stale_duplicate([first, second]), False, "stale_duplicate_dataset")
        first["referenced"] = False
        self.assert_result(no_stale_duplicate([first, second]), True, "stale_duplicate_dataset")

    def test_manifest_not_assessable(self):
        for entries in (None, [], [{}], [self.entry(sha256="bad")], [self.entry(version=None)]):
            self.assert_unknown(no_stale_duplicate(entries))

    def test_bounds_feasible_including_endpoints(self):
        for target in (0, 1, 0.95, "1/3", Fraction(2, 3)):
            self.assert_result(bound_feasible((0, 1), target), True, "infeasible_bound")

    def test_bounds_infeasible(self):
        for target in ("10000000000000001/10000000000000000", -1, 95):
            self.assert_result(bound_feasible((0, 1), target), False, "infeasible_bound")

    def test_bounds_rational_precision(self):
        self.assert_result(bound_feasible(("1/3", "1/3"), Fraction(1, 3)), True, "infeasible_bound")
        self.assert_result(bound_feasible(("1/3", "1/3"), 0.3333333333333333), False, "infeasible_bound")
        self.assert_result(bound_feasible((0.1, 0.3), "3/10"), True, "infeasible_bound")

    def test_bounds_not_assessable(self):
        for interval, target in ((None, 1), ((0, 1), None), ([], 1), ((1, 0), 1),
                                 ((0, 1), float("nan")), ((0, 1), "1/0"), ((0, 1), True)):
            self.assert_unknown(bound_feasible(interval, target))

    def test_baseline_tie_break_option(self):
        labels = ["b", "a", "b", "a", "c"]
        self.assert_unknown(baseline_consistent("majority_class", ["a"], labels))
        self.assert_result(baseline_consistent("majority_class:tie=lowest", ["a", "a"], labels), True,
                           "baseline_definition_conflict")
        self.assert_result(baseline_consistent("majority_class:tie=highest", ["b"], labels), True,
                           "baseline_definition_conflict")
        self.assert_result(baseline_consistent("majority_class:tie=lowest", ["b"], labels), False,
                           "baseline_definition_conflict")
        self.assert_result(baseline_consistent("minority_class:tie=highest", ["c"], ["a", "b", "a", "b", "c", "d"]
                                               ), False, "baseline_definition_conflict")
        # numbers order numerically, not as text; the captured baseline is the lowest label
        numeric = [10, 9, 10, 9]
        self.assert_result(baseline_consistent("majority_class:tie=lowest", [9.0], numeric), True,
                           "baseline_definition_conflict")
        # no tie: the option changes nothing
        self.assert_result(baseline_consistent("majority_class:tie=highest", ["x"], ["x", "x", "y"]), True,
                           "baseline_definition_conflict")
        for bad in ("majority_class:tie=first", "majority_class:tie=", "majority_class:other=lowest"):
            self.assert_unknown(baseline_consistent(bad, ["a"], labels))
        self.assert_unknown(baseline_consistent("majority_class:tie=lowest", ["a"], ["a", 1, "a", 1]))

    def test_baseline_tie_break_matches_the_captured_rule(self):
        labels = ["no", "yes", "yes", "no", "maybe"]
        captured = max(sorted(set(labels)), key=labels.count)
        self.assert_result(baseline_consistent("majority_class:tie=lowest", [captured] * 3, labels), True,
                           "baseline_definition_conflict")

    def snapshot(self, files):
        from jiuwenswarm.research.state import json_bytes
        record = {"schema_version": "1.0.0", "id": "baseline", "kind": "supplied baseline", "origin": "local",
                  "revision": "r1", "access": "read-only", "license": "unknown", "availability": "available",
                  "environment_ref": None,
                  "files": [{"path": path, "artifact_ref": {"id": "blob:" + hashlib.sha256(data).hexdigest(),
                                                           "sha256": hashlib.sha256(data).hexdigest()},
                             "media_type": "text/plain", "audience": "researcher"} for path, data in sorted(files.items())]}
        return record, {"id": "baseline", "sha256": hashlib.sha256(json_bytes(record)).hexdigest()}

    def test_snapshot_matches_pins_the_record_not_a_file(self):
        files = {"a.csv": b"x\n1\n", "b.txt": b"hello"}
        record, pin = self.snapshot(files)
        self.assert_result(snapshot_matches(record, pin, files), True, "pin_mismatch")
        self.assert_result(snapshot_matches(record, pin["sha256"].upper(), files), True, "pin_mismatch")
        # Hashing a file's bytes against the pin is the old wrong check: it must not pass here.
        self.assert_result(pin_matches(files["a.csv"], pin["sha256"]), False, "pin_mismatch")
        # key order of the stored record does not matter, the canonical bytes do
        self.assert_result(snapshot_matches(dict(reversed(list(record.items()))), pin, files), True, "pin_mismatch")

    def test_snapshot_matches_detects_record_and_file_drift(self):
        files = {"a.csv": b"x\n1\n", "b.txt": b"hello"}
        record, pin = self.snapshot(files)
        edited = deepcopy(record)
        edited["revision"] = "r2"
        result = snapshot_matches(edited, pin, files)
        self.assert_result(result, False, "pin_mismatch")
        self.assertEqual(result["evidence"][0]["level"], "snapshot_record")
        result = snapshot_matches(record, pin, dict(files, **{"a.csv": b"x\n2\n"}))
        self.assert_result(result, False, "pin_mismatch")
        self.assertEqual([(row["level"], row["path"]) for row in result["evidence"]], [("file", "a.csv")])
        result = snapshot_matches(record, pin, dict(files, extra=b"?"))
        self.assert_result(result, False, "pin_mismatch")
        self.assertIn("not listed", result["evidence"][0]["reason"])
        # a file entry edited together with the record still fails the pin
        forged = deepcopy(record)
        forged["files"][0]["artifact_ref"] = {"id": "blob:x", "sha256": hashlib.sha256(b"forged").hexdigest()}
        self.assert_result(snapshot_matches(forged, pin, dict(files, **{"a.csv": b"forged"})), False, "pin_mismatch")

    def test_snapshot_matches_not_assessable(self):
        files = {"a.csv": b"x"}
        record, pin = self.snapshot(files)
        for args in [(None, pin, files), (record, None, files), (record, pin, None), (record, "abc", files),
                     ({"files": "no"}, pin, files), (record, pin, {}), (record, pin, {"a.csv": "text"}),
                     (dict(record, files=[{"path": "a.csv"}]), pin, files),
                     (dict(record, files=record["files"] * 2), pin, files),
                     (dict(record, bad=float("nan")), pin, files)]:
            with self.subTest(args=str(args)[:60]):
                self.assert_unknown(snapshot_matches(*args))


if __name__ == "__main__":
    unittest.main()
