"""Check the frozen matched delivery and its standalone design validators."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
RECEIPT = json.loads((HERE / "comparison.json").read_text(encoding="utf-8"))
REPO = HERE.parents[3]
ROOTS = {
    "full": Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else (HERE / RECEIPT["full_root"]).resolve(),
    "compact": Path(sys.argv[2]).resolve() if len(sys.argv) > 2 else (HERE / RECEIPT["compact_root"]).resolve(),
}


def inventory(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in root.rglob("*")
        if path.is_file()
    }


for name, root in ROOTS.items():
    assert root.is_dir(), f"missing {name} package: {root}"
    assert inventory(root) == RECEIPT[f"{name}_files"], f"package bytes differ from receipt: {name}"
    assert sum(len((root / item).read_text(encoding="utf-8").split()) for item in RECEIPT["explanatory_files"]) == RECEIPT["words"][name]
    assert sum(len((root / item).read_text(encoding="utf-8").split()) for item in RECEIPT["orientation_files"]) == RECEIPT["orientation_words"][name]
    assert sum(len((root / item).read_text(encoding="utf-8").split()) for item in RECEIPT["entrypoint_files"]) == RECEIPT["entrypoint_words"][name]

full, compact = ROOTS["full"], ROOTS["compact"]
assert len(RECEIPT["shared_files"]) == len(set(RECEIPT["shared_files"]))
for item in RECEIPT["shared_files"]:
    assert (full / item).read_bytes() == (compact / item).read_bytes(), f"shared bytes differ: {item}"

for item, expected in RECEIPT["preserved_schema_files"].items():
    full_bytes = (full / item).read_bytes()
    compact_bytes = (compact / item).read_bytes()
    assert full_bytes == compact_bytes, f"schema differs between packages: {item}"
    assert hashlib.sha256(full_bytes).hexdigest() == expected, f"schema hash differs from recorded base: {item}"
    original_path = f"{RECEIPT['base_full_repo_root']}/{item}"
    original = subprocess.check_output(["git", "-C", str(REPO), "show", f"{RECEIPT['base_commit']}:{original_path}"])
    assert full_bytes == original, f"pre-existing schema changed since base: {item}"

for item, expected in RECEIPT["external_sources"].items():
    actual = hashlib.sha256((REPO / item).read_bytes()).hexdigest()
    assert actual == expected, f"external source hash differs: {item}"

for name, root in ROOTS.items():
    subprocess.run([sys.executable, str(root / "reference" / "validate.py"), str(root)], check=True)

print(
    "PASS matched package inventories, shared bytes, unchanged schemas, source receipts, "
    "reading measurements, and standalone validators"
)
print("LIMIT documentation and synthetic contract consistency only; no runtime or product acceptance")
