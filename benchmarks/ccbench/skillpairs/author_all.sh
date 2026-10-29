#!/bin/bash
# Blind skill authoring: each author sees ONLY author_prompt.txt and its outcome spec, in an empty directory.
# Usage: author_all.sh OUT_DIR   (skills are written to OUT_DIR/skills; nothing is written beside this script;
# model calls: one `codex exec` per skill, so run it deliberately).
set -u
here=$(cd "$(dirname "$0")" && pwd)
out=${1:?usage: author_all.sh OUT_DIR}
codex=${AI4R_CODEX_BIN:-codex}
command -v "$codex" >/dev/null 2>&1 || [ -x "$codex" ] || { echo "codex not found: set AI4R_CODEX_BIN or put codex on PATH" >&2; exit 2; }
mkdir -p "$out/skills"
cd "$out"
for x in X1-evaluate X2-screen X3-plan X4-intent X5-deliver; do
  d=skills/$x; mkdir -p $d
  [ -f $d/SKILL.md ] && continue
  cat "$here/author_prompt.txt" <(echo; echo "OUTCOME:"; cat "$here/specs/$x.md") | "$codex" exec --skip-git-repo-check -C $d -s workspace-write --ephemeral -o $d/.author-reply.txt - > $d/.author-log.txt 2>&1
  echo "$x exit $?" >> skills/authoring.log
done
echo DONE >> skills/authoring.log
