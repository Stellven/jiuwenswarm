"""Focused integrity-checker regression tests; standard-library only."""
import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

CHECKER = Path(__file__).with_name("check_package.py")
SPEC = importlib.util.spec_from_file_location("check_package", CHECKER)
checker = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(checker)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class PackageFixture:
    def __init__(self, root):
        self.root = root
        (root / "_tools").mkdir()
        (root / "sources/live-program/TRIAL-1").mkdir(parents=True)
        (root / "sources/main-baseline").mkdir(parents=True)
        (root / "sources/main-baseline/M1-001.md").write_text("# M1-001\n", encoding="utf-8")
        (root / "authority-index.md").write_text("# Authorities\n", encoding="utf-8")
        (root / "sources/live-program/TASKS.md").write_text(
            "| TASK | Outcome | Feature | Status |\n|---|---|---|---|\n"
            "| [TRIAL-1](TRIAL-1/TASK.md) | Intent verifier | `docs/code/Missions/M1/TRIAL-1/` | Registered |\n"
            "| [M1-001](../main-baseline/M1-001.md) | Bounded authenticated Codex CLI model invocation | main | Active |\n", encoding="utf-8")
        (root / "sources/live-program/TRIAL-1/TASK.md").write_text(
            "# TASK: TRIAL-1\nFeature `docs/code/Missions/M1/TRIAL-1/`\nTRIAL-IF-001\n", encoding="utf-8")
        prd_ids = [f"1.{n}" for n in range(1, 185)]
        (root / "sources/product-prd.txt").write_text(
            "\n".join(f"## {ident} Requirement {ident}" for ident in prd_ids), encoding="utf-8")
        rows = ["| Source clause ID / exact locator | Architecture responsibility | Existing owning TASK / AC references | Allocation decision and completeness |", "|---|---|---|---|"]
        rows.extend(f"| §{ident} Requirement | Design page | Owner | Mapped |" for ident in prd_ids)
        (root / "coverage-allocation.md").write_text("\n".join(rows), encoding="utf-8")
        stage_rows = ["# Delivery", "| Delivery / implementation stage | Inputs | Runnable exit | Allocation |", "|---|---|---|---|"]
        stage_rows.extend(f"| Phase 1, Stage {n} (§6.{n + 3}): stage | input | exit | owner |" for n in range(8))
        stage_rows.append("| Phase 2, Stage 8 (§6.11): stage | input | exit | owner |")
        stage_rows.extend(["## Phase 3 is accounted M1 work", "| Expected effort | Reuse | Evidence |", "|---|---|---|"])
        stage_rows.extend(f"| {name} | Existing boundary | evidence |" for name in ["Advanced intention compiler", "Agent Team / Cluster planning", "Dynamic CC discovery/binding", "Heterogeneous model routing", "Alternate verifier", "Applicable OpenJiuwen Code Mode"])
        (root / "delivery-phases.md").write_text("\n".join(stage_rows), encoding="utf-8")
        (root / "references.md").write_text("# Root\n## Anchor\n[img]: images/pixel.png\n\n![image][img]\n[Shortcut]\n[Shortcut]: child.md#hello%2Dworld\n", encoding="utf-8")
        (root / "child.md").write_text("# Child\n## Hello World\n", encoding="utf-8")
        (root / "notes.txt").write_text("See [child](child.md#hello%2Dworld) and ![image](images/pixel.png).\n", encoding="utf-8")
        (root / "images").mkdir()
        (root / "images/pixel.png").write_bytes(b"png")
        (root / "sources/main-baseline/snapshot.md").write_text("snapshot\n", encoding="utf-8")
        commit = "a" * 40
        snapshot = {"path": "sources/main-baseline/snapshot.md", "origin": "docs/snapshot.md", "repository": "target-main", "commit": commit, "sha256": sha(root / "sources/main-baseline/snapshot.md"), "source_sha256": sha(root / "sources/main-baseline/snapshot.md")}
        (root / "_tools/snapshot-inputs.json").write_text(json.dumps({"snapshots": [snapshot]}), encoding="utf-8")
        projections = []
        for path, origin, contents in [
            ("sources/live-program/TASKS.md", "docs/code/Missions/M1/TASKS.md", (root / "sources/live-program/TASKS.md").read_text(encoding="utf-8")),
            ("sources/live-program/TRIAL-1/TASK.md", "docs/code/Missions/M1/TRIAL-1/TASK.md", (root / "sources/live-program/TRIAL-1/TASK.md").read_text(encoding="utf-8")),
        ]:
            p = root / path
            projections.append({"path": path, "origin": origin, "source_sha256": sha(p), "sha256": sha(p)})
        authority_paths = ["docs/code/Missions/M1/TASKS.md", "docs/code/Missions/M1/TRIAL-1/TASK.md", "docs/code/Code_SOP.md", "docs/code/SPEC_KIT_WORKFLOW.md", "docs/code/VERIFICATION.md", ".specify/memory/constitution.md", "plugins/spec-kit/README.md"]
        files = []
        for p in sorted(root.rglob("*")):
            if p.is_file() and p.name not in {"package-manifest.json", "source-baseline.json"}:
                files.append({"path": p.relative_to(root).as_posix(), "sha256": sha(p)})
        core = [{"path": p.relative_to(root).as_posix(), "sha256": sha(p)} for p in sorted(root.rglob("*.md")) if "sources" not in p.relative_to(root).parts]
        canonical = json.dumps(core, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        aggregate = hashlib.sha256(canonical.encode()).hexdigest()
        baseline = {"architecture": core, "architecture_aggregate_sha256": aggregate}
        (root / "source-baseline.json").write_text(json.dumps(baseline), encoding="utf-8")
        files.append({"path": "source-baseline.json", "sha256": sha(root / "source-baseline.json")})
        for path in authority_paths:
            (root / "authority-index.md").parent.mkdir(parents=True, exist_ok=True)
        manifest = {"current_prd": {"path": "sources/product-prd.txt", "sha256": sha(root / "sources/product-prd.txt")},
                    "target_main": commit, "snapshots": [snapshot], "live_projections": projections,
                    "live_authorities": [{"path": p} for p in authority_paths],
                    "source_baseline": {"path": "source-baseline.json", "sha256": sha(root / "source-baseline.json"), "architecture_aggregate_sha256": aggregate},
                    "files": files}
        (root / "package-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")


class CheckerTests(unittest.TestCase):
    def test_txt_reference_shortcut_image_and_fragments_pass_then_bad_links_inventory_and_hash_fail(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            PackageFixture(root)
            initial = self.run_checker(root)
            self.assertEqual(initial["status"], "PASS", initial["errors"])
            (root / "notes.txt").write_text("[bad](child.md#missing) [escape](../outside.md)\n", encoding="utf-8")
            manifest = json.loads((root / "package-manifest.json").read_text(encoding="utf-8"))
            manifest["files"] = [x for x in manifest["files"] if x["path"] != "images/pixel.png"]
            manifest["files"][0]["sha256"] = "0" * 64
            (root / "package-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            result = self.run_checker(root)
            self.assertEqual(result["status"], "FAIL")
            errors = "\n".join(result["errors"])
            self.assertIn("missing fragment", errors)
            self.assertIn("escapes package", errors)
            self.assertIn("SHA-256 mismatch", errors)
            self.assertIn("manifest omits", errors)

    def test_missing_provenance_or_authorities_and_false_coverage_fail(self):
        for mutation in ("snapshots", "live_projections", "live_authorities", "baseline", "stages", "efforts", "registration", "duplicate_mapping"):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as d:
                root = Path(d)
                PackageFixture(root)
                manifest_path = root / "package-manifest.json"
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                if mutation in ("snapshots", "live_projections", "live_authorities"):
                    manifest[mutation] = []
                elif mutation == "baseline":
                    manifest["source_baseline"].pop("architecture_aggregate_sha256")
                elif mutation in ("stages", "efforts"):
                    path = root / "delivery-phases.md"
                    text = path.read_text(encoding="utf-8")
                    text = text.replace("Stage 8", "Milestone Eight") if mutation == "stages" else text.replace("Alternate verifier", "Unrelated row")
                    path.write_text(text, encoding="utf-8")
                elif mutation == "registration":
                    path = root / "sources/live-program/TASKS.md"
                    path.write_text(path.read_text(encoding="utf-8").replace("[TRIAL-1]", "[M1-001]"), encoding="utf-8")
                else:
                    path = root / "coverage-allocation.md"
                    path.write_text(path.read_text(encoding="utf-8") + "\n| §1.1 Requirement | Design | Owner | Mapped |\n", encoding="utf-8")
                manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
                result = self.run_checker(root)
                self.assertEqual(result["status"], "FAIL")
                errors = "\n".join(result["errors"])
                expected = {"snapshots":"snapshots must be a nonempty", "live_projections":"live_projections must contain", "live_authorities":"live_authorities must list", "baseline":"aggregate", "stages":"explicit table row", "efforts":"six named", "registration":"exactly one TRIAL-1", "duplicate_mapping":"exactly one complete"}[mutation]
                self.assertIn(expected, errors)

    @staticmethod
    def run_checker(root):
        import contextlib, io, sys
        old_argv = sys.argv
        try:
            sys.argv = [str(CHECKER), "--root", str(root)]
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                checker.main()
            return json.loads(out.getvalue())
        finally:
            sys.argv = old_argv


if __name__ == "__main__":
    unittest.main()
