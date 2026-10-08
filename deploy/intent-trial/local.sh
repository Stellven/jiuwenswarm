#!/bin/sh
# Operate the existing supported local container without importing host auth.
set -eu
export PATH=/usr/sbin:/usr/bin:/sbin:/bin

ACTION=${1:-status}
EVIDENCE=${2:-/var/lib/ai4research-trial/definition-evidence-LOCAL-3}
PROJECT=ai4research-m0
KEEPER_DIR=/run/ai4research-m0-keeper
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
COMPOSE_FILE=$SCRIPT_DIR/compose.yml

fail() {
    printf '%s\n' "$1" >&2
    exit 1
}

case "$ACTION" in start|status|token|stop|rebuild|prepare-keeper|keepalive) ;; *) fail 'Use start, status, token, stop or rebuild.' ;; esac
test "$#" -le 2 || fail 'Unexpected launcher arguments.'
test "$(id -u)" = 0 || fail 'Run this host launcher through wsl -d Ubuntu -u root.'
command -v docker >/dev/null 2>&1 || fail 'Docker Engine is not installed in this distribution.'
test -f "$COMPOSE_FILE" || fail 'The local Compose definition is missing.'

case "$EVIDENCE" in /*) ;; *) fail 'Definition evidence must use an absolute Linux path.' ;; esac
export TRIAL_DEFINITION_EVIDENCE_DIR=$EVIDENCE

compose() {
    docker compose --project-name "$PROJECT" --file "$COMPOSE_FILE" "$@"
}

container_id() {
    compose ps --all --quiet intent-trial
}

daemon_ready() {
    docker info >/dev/null 2>&1
}

ensure_daemon() {
    if ! daemon_ready; then
        command -v systemctl >/dev/null 2>&1 || fail 'Docker daemon is unavailable.'
        systemctl start docker
        daemon_ready || fail 'Docker daemon did not become ready.'
    fi
}

keeper_custody() {
    if test ! -e "$KEEPER_DIR"; then
        (umask 077; mkdir -- "$KEEPER_DIR") || test -d "$KEEPER_DIR" || fail 'The private keepalive directory is unavailable.'
    fi
    test ! -L "$KEEPER_DIR" && test -d "$KEEPER_DIR" || fail 'The keepalive directory is redirected.'
    test "$(realpath -e -- "$KEEPER_DIR")" = "$KEEPER_DIR" || fail 'The keepalive directory traverses a redirect.'
    test "$(stat -c %u -- "$KEEPER_DIR")" = 0 && test "$(stat -c %a -- "$KEEPER_DIR")" = 700 || fail 'Keepalive custody must be root-owned and private0700.'
    for item in "$KEEPER_DIR/lock" "$KEEPER_DIR/pid" "$KEEPER_DIR/stop"; do
        if test -e "$item" || test -L "$item"; then
            test ! -L "$item" && test -f "$item" || fail 'A keepalive custody file is redirected or unsupported.'
            test "$(stat -c %u -- "$item")" = 0 && test "$(stat -c %a -- "$item")" = 600 && test "$(stat -c %h -- "$item")" = 1 || fail 'Keepalive custody files must be root-owned single-linked0600.'
        fi
    done
}

prepare_keeper() {
    keeper_custody
    # This exact root-private sentinel is the only stop signal we remove.
    if test -f "$KEEPER_DIR/stop"; then
        rm -- "$KEEPER_DIR/stop"
    fi
}

keepalive() {
    # A foreground Linux process prevents WSL idle shutdown; it performs no work.
    keeper_custody
    command -v flock >/dev/null 2>&1 || fail 'The owned keepalive requires flock.'
    umask 077
    exec 9>"$KEEPER_DIR/lock"
    flock -n 9 || return 0
    test ! -f "$KEEPER_DIR/stop" || return 0
    tick=$(awk '{print $22}' "/proc/$$/stat")
    boot=$(cat /proc/sys/kernel/random/boot_id)
    temporary=$KEEPER_DIR/pid.$$
    (set -C; printf '%s\n%s\n%s\n' "$$" "$tick" "$boot" > "$temporary") || fail 'Keepalive identity could not be recorded.'
    mv -- "$temporary" "$KEEPER_DIR/pid"
    cleanup_keeper() {
        # Never signal a PID; remove only our still-matching marker.
        if test -f "$KEEPER_DIR/pid" && test ! -L "$KEEPER_DIR/pid"; then
            recorded_pid=$(sed -n '1p' "$KEEPER_DIR/pid")
            recorded_tick=$(sed -n '2p' "$KEEPER_DIR/pid")
            recorded_boot=$(sed -n '3p' "$KEEPER_DIR/pid")
            if test "$recorded_pid" = "$$" && test "$recorded_tick" = "$tick" && test "$recorded_boot" = "$boot"; then
                rm -- "$KEEPER_DIR/pid"
            fi
        fi
    }
    trap cleanup_keeper 0
    trap 'exit 0' 1 2 15
    seen_running=false
    grace=60
    while test ! -f "$KEEPER_DIR/stop"; do
        cid=$(container_id 2>/dev/null || true)
        running=false
        if test -n "$cid"; then
            running=$(docker inspect --format '{{.State.Running}}' "$cid" 2>/dev/null || printf false)
        fi
        if test "$running" = true; then
            seen_running=true
        elif test "$seen_running" = true || test "$grace" -le 0; then
            break
        else
            grace=$((grace - 1))
        fi
        sleep 2
    done
}

stop_keeper() {
    keeper_custody
    # The helper observes this root-private sentinel and exits by itself.
    (umask 077; printf 'stop\n' > "$KEEPER_DIR/stop")
}

validate_evidence() {
    test -d "$EVIDENCE" || fail 'The private definition evidence folder is missing; prepare it first.'
    test "$(realpath -e -- "$EVIDENCE")" = "$EVIDENCE" || fail 'Definition evidence must not traverse redirects or ambiguous paths.'
    test -f "$EVIDENCE/definition-admission.json" || fail 'The retained definition admission receipt is missing.'
    # All files belong to the application UID; no symlinks or special objects.
    find "$EVIDENCE" -exec sh -c '
        for item do
            test ! -L "$item" || exit 1
            test "$(stat -c %u -- "$item")" = 10001 || exit 1
            if test -d "$item"; then
                test "$(stat -c %a -- "$item")" = 700 || exit 1
            elif test -f "$item"; then
                test "$(stat -c %a -- "$item")" = 600 || exit 1
                test "$(stat -c %h -- "$item")" = 1 || exit 1
            else
                exit 1
            fi
        done
    ' sh {} + || fail 'Definition evidence custody must be UID10001, directories0700 and single-linked files0600.'
}

check_port() {
    command -v ss >/dev/null 2>&1 || fail 'The host socket inventory tool ss is required.'
    listeners=$(ss -H -ltnp '( sport = :4311 )')
    test -n "$listeners" || return 0
    cid=$(container_id)
    test -n "$cid" || fail 'Port4311 is already occupied by another process; nothing was stopped.'
    pid=$(docker inspect --format '{{.State.Pid}}' "$cid")
    case "$pid" in ''|0|*[!0-9]*) fail 'Port4311 is occupied outside the current application; nothing was stopped.' ;; esac
    # This image runs the Python service as its main process, without a proxy.
    while IFS= read -r listener; do
        case "$listener" in *"pid=$pid,"*) ;; *) fail 'Port4311 has an unrelated listener; nothing was stopped.' ;; esac
    done <<EOF
$listeners
EOF
}

check_admission() {
    # A disposable offline check reads exact definitions and retained evidence.
    # It never starts the model runtime or mutates the durable state volume.
    compose run --rm --no-deps -T --entrypoint python intent-trial - <<'PY_ADMISSION'
import sys
from pathlib import Path
from jiuwenswarm.ai4research.admission import validate_admission_receipt
from jiuwenswarm.ai4research.capsules import CapsuleLibrary
from jiuwenswarm.ai4research.common import GovernanceError
try:
    definitions = CapsuleLibrary("/tmp/launcher-preflight.sqlite", Path("/app/jiuwenswarm/ai4research")).seed_builtin()
    pins = {"compiler": definitions["intent_compiler"], "verifier": definitions["intent_verifier"]}
    validate_admission_receipt(Path("/definition-evidence/definition-admission.json"), pins)
    print("Current definitions match the retained provisional admission evidence; no real-model acceptance is implied.")
except GovernanceError as exc:
    print("Definition admission preflight failed: " + exc.code, file=sys.stderr)
    sys.exit(1)
except Exception:
    print("Definition admission preflight is unavailable.", file=sys.stderr)
    sys.exit(1)
PY_ADMISSION
}

status() {
    if ! daemon_ready; then
        printf '%s\n' '{"connection_state":"docker_daemon_unavailable","ready":false}'
        return 1
    fi
    cid=$(container_id)
    if test -z "$cid" || test "$(docker inspect --format '{{.State.Running}}' "$cid")" != true; then
        printf '%s\n' '{"connection_state":"application_stopped","ready":false}'
        return 1
    fi
    compose exec -T intent-trial python - <<'PY_STATUS'
import json
import os
import stat
import sys
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, Request, build_opener

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

def word(value):
    # Only stable ASCII status codes/IDs cross this diagnostic boundary.
    if isinstance(value, str) and 0 < len(value) <= 128 and all(c.isalnum() or c in "_-./ :" for c in value) and value.isascii():
        return value
    return "unavailable"

def state(value):
    value = value if isinstance(value, dict) else {}
    return {"ready": value.get("ready") is True, "reason": word(value.get("reason", "not_reported"))}

try:
    path = Path("/state/session.token")
    before = path.lstat()
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, "rb") as stream:
        info = os.fstat(stream.fileno())
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o600 or info.st_nlink != 1
                or (info.st_dev, info.st_ino) != (before.st_dev, before.st_ino)):
            raise ValueError()
        token = stream.read(1025).decode("utf-8")
        after = path.lstat()
        if (info.st_dev, info.st_ino) != (after.st_dev, after.st_ino):
            raise ValueError()
    if not 32 <= len(token) <= 1024 or not all(c.isascii() and (c.isalnum() or c in "-_") for c in token):
        raise ValueError()
    req = Request("http://127.0.0.1:4311/api/intent-trial/readiness", headers={"Authorization": "Bearer " + token})
    with build_opener(NoRedirect()).open(req, timeout=8) as response:
        body = response.read(262145)
    if len(body) > 262144:
        raise ValueError()
    health = json.loads(body)
    model = health.get("model", {})
    ids = [word(item.get("id")) for item in model.get("models", [])[:64] if isinstance(item, dict)]
    out = {
        "connection_state": "connected" if health.get("ready") is True else "connected_prerequisites_pending",
        "scope": word(health.get("scope")),
        "ready": health.get("ready") is True,
        "mock": health.get("mock") is True,
        "storage": state(health.get("storage")),
        "identity_security": state(health.get("identity_security")),
        "definition_admission": state(health.get("definition_admission")),
        "definitions": word(health.get("definitions")),
        "model": {"ready": model.get("ready") is True, "security_ready": model.get("security_ready") is True,
                  "authentication": word(model.get("authentication")), "ipc": word(model.get("ipc")),
                  "runtime": word(model.get("runtime")), "model_ids": ids},
    }
    print(json.dumps(out, indent=2))
except HTTPError as exc:
    print(json.dumps({"connection_state": "authentication_required" if exc.code in (401,403) else "http_unavailable", "ready": False, "http_status": exc.code}))
    sys.exit(1)
except Exception:
    print('{"connection_state":"local_readiness_unavailable","ready":false}')
    sys.exit(1)
PY_STATUS
}

wait_for_page() {
    compose exec -T intent-trial python - <<'PY_PAGE'
import sys
import time
from urllib.request import urlopen
for attempt in range(20):
    try:
        with urlopen("http://127.0.0.1:4311/intent-trial", timeout=2) as response:
            body = response.read(1048577)
            if response.status == 200 and len(body) <= 1048576 and b"<html" in body.lower():
                print("Native local page is available at http://127.0.0.1:4311/intent-trial")
                sys.exit(0)
    except Exception:
        pass
    time.sleep(1)
print("Native local page did not become available; inspect the local container status.", file=sys.stderr)
sys.exit(1)
PY_PAGE
}

case "$ACTION" in
    start|rebuild)
        ensure_daemon
        validate_evidence
        check_port
        if test "$ACTION" = rebuild; then
            compose build intent-trial
        fi
        check_admission
        compose up --detach --no-build intent-trial
        wait_for_page
        status
        ;;
    status)
        status
        ;;
    token)
        # Only the PowerShell Open action consumes this private captured pipe.
        test "${TRIAL_TOKEN_PIPE:-}" = clipboard-v1 || fail 'Session delivery is available only through the PowerShell Open action.'
        daemon_ready || fail 'Docker daemon is unavailable.'
        compose exec -T intent-trial python - <<'PY_TOKEN'
import os
import stat
import sys
from pathlib import Path
try:
    path = Path("/state/session.token")
    before = path.lstat()
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, "rb") as stream:
        info = os.fstat(stream.fileno())
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o600 or info.st_nlink != 1 or sys.stdout.isatty()
                or (info.st_dev, info.st_ino) != (before.st_dev, before.st_ino)):
            raise ValueError()
        token = stream.read(1025).decode("utf-8")
        after = path.lstat()
        if (info.st_dev, info.st_ino) != (after.st_dev, after.st_ino):
            raise ValueError()
    if not 32 <= len(token) <= 1024 or not all(c.isascii() and (c.isalnum() or c in "-_") for c in token):
        raise ValueError()
    sys.stdout.write(token)
except Exception:
    print("Private local session delivery is unavailable.", file=sys.stderr)
    sys.exit(1)
PY_TOKEN
        ;;
    stop)
        daemon_ready || fail 'Docker daemon is unavailable; no running application was changed.'
        compose stop intent-trial
        stop_keeper
        printf '%s\n' 'Application stopped. Durable state, workspace and dedicated model profile are preserved.'
        ;;
    prepare-keeper)
        prepare_keeper
        ;;
    keepalive)
        keepalive
        ;;
esac
