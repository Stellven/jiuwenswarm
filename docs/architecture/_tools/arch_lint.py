"""Read-only checks for the slim architecture; no schema or page generation."""

import argparse
import re
from pathlib import Path
from urllib.parse import unquote, urlsplit


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("docs", nargs="?", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--check", action="store_true", help="Compatibility flag; all runs are read-only")
    parser.add_argument("--max-words", type=int, help="Optional word budget, including diagram source")
    args = parser.parse_args()
    root = args.docs.resolve()
    pages = sorted(root.rglob("*.md"))
    problems = []
    total = 0
    prose_total = 0
    diagrams = 0
    if not pages:
        problems.append("No architecture Markdown pages found")
    for page in pages:
        source = page.read_text(encoding="utf-8")
        total += len(re.findall(r"\b[\w]+(?:[-'][\w]+)*\b", source))
        if source.count("```") % 2:
            problems.append(f"{page.name}: unclosed code fence")
        prose = re.sub(r"```.*?```", "", source, flags=re.S)
        prose_total += len(re.findall(r"\b[\w]+(?:[-'][\w]+)*\b", re.sub(r"\[([^]]+)\]\([^)]+\)", r"\1", prose)))
        for target in re.findall(r"\]\(([^)]+)\)", prose):
            parsed = urlsplit(target)
            if parsed.scheme or parsed.netloc or not parsed.path:
                continue
            resolved = (page.parent / unquote(parsed.path)).resolve()
            if not resolved.exists():
                problems.append(f"{page.name}: missing link {target}")
        for diagram in re.findall(r"```mermaid\s*\n(.*?)```", source, flags=re.S):
            diagrams += 1
            if "subgraph Legend[Legend]" not in diagram or "classDef " not in diagram:
                problems.append(f"{page.name}: diagram needs colors and a legend")
    if args.max_words is not None and total > args.max_words:
        problems.append(f"Word budget exceeded: {total} > {args.max_words} (including diagram source)")
    print(f"{len(pages)} pages; {prose_total} prose words; {total} words including diagram source; {diagrams} Mermaid diagrams")
    for problem in problems:
        print(problem)
    print("FAIL" if problems else "ok")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
