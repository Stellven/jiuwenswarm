# skillpairs: blind-authored ordinary skills

Skill folders (`skills/X1..X5`) and outcome specs (`specs/`) used by planbench (X3-plan is the frozen planning skill) and nativetask (`--skill-dir`).

## Origin (ccbench copy)

Copied from cc-sweep-20261026/skillpairs (sha256 in BASELINE-CODE-MANIFEST), changes:

- `author_all.sh` takes `OUT_DIR` and no longer `cd`s into a Windows path; it uses `AI4R_CODEX_BIN` or `codex` on PATH. It makes model calls (one per skill), so run it deliberately.
- Authoring logs (`.author-log.txt`, `.author-reply.txt`, `skills/authoring.log`) are not copied; they stay in the old evidence root.
- The `SKILL.md` files are byte-identical to the old ones (planbench `freeze.py --check` hashes X3-plan).
