#!/usr/bin/env bash
# Allocate only the local application's cgroup-v2 branch. No generated code
# receives this mount, a daemon credential, or a host cgroup root.
set -euo pipefail
[[ "$(id -u)" == 0 ]] || { printf 'Run local executor preparation as the Linux host root.\n' >&2; exit 2; }

root=/sys/fs/cgroup
project="${AI4R_EXECUTOR_PROJECT:-ai4r-web-play}"
[[ "$project" =~ ^ai4r-[a-z0-9_-]+$ && ${#project} -le 48 ]] || {
  printf 'Invalid owned executor project.\n' >&2; exit 2;
}
target="$root/$project-executor"
owner="/run/$project-executor.owner"
identity="$project:cgroup-v2:1"
[[ "$(stat -f -c %T "$root")" == cgroup2fs ]] || { printf 'A real cgroup-v2 host is required.\n' >&2; exit 2; }
[[ ! -L "$root" && "$(readlink -f "$root")" == "$root" ]] || exit 2

if [[ -e "$owner" ]]; then
  [[ -f "$owner" && ! -L "$owner" && "$(stat -c %u:%a:%h "$owner")" == 0:600:1 && "$(cat "$owner")" == "$identity" ]] || {
    printf 'Existing local executor owner marker has invalid custody.\n' >&2; exit 2;
  }
elif [[ -e "$target" ]]; then
  printf 'The existing cgroup branch has no local application owner marker; refusing to adopt it.\n' >&2
  exit 2
else
  (umask 077; set -o noclobber; printf '%s\n' "$identity" > "$owner")
fi

if [[ ! -e "$target" ]]; then
  mkdir -- "$target"
fi
[[ -d "$target" && ! -L "$target" && "$(readlink -f "$target")" == "$target" && "$(stat -c %u "$target")" == 0 ]] || exit 2
[[ -z "$(cat "$target/cgroup.procs")" ]] || { printf 'The executor delegation itself contains a process; refusing to change it.\n' >&2; exit 2; }
for controller in memory pids; do
  [[ " $(cat "$target/cgroup.controllers") " == *" $controller "* ]] || {
    printf 'The local executor requires the %s cgroup controller.\n' "$controller" >&2; exit 2;
  }
done
printf '+memory +pids\n' > "$target/cgroup.subtree_control"
printf '%s\n' "$target"
