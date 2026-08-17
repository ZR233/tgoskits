#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname "$0")" && pwd)
. "$SCRIPT_DIR/../apache-runner-lib.sh"

CALL_LOG=$(mktemp)
trap 'rm -f "$CALL_LOG"' EXIT

curl() {
    printf 'curl' > "$CALL_LOG"
    printf ' %s' "$@" >> "$CALL_LOG"
    printf '\n' >> "$CALL_LOG"
}

timeout_stub() {
    printf 'timeout' > "$CALL_LOG"
    printf ' %s' "$@" >> "$CALL_LOG"
    printf '\n' >> "$CALL_LOG"
}

APACHE_RUNNER_TIMEOUT_CMD=timeout_stub
apache_runner_run_with_timeout 7 curl -fsS http://127.0.0.1:8080/

expected='curl --max-time 7 -fsS http://127.0.0.1:8080/'
actual=$(cat "$CALL_LOG")
[ "$actual" = "$expected" ] || {
    printf 'expected: %s\nactual:   %s\n' "$expected" "$actual" >&2
    exit 1
}

apache_runner_run_with_timeout 3 sh -c true

expected='timeout 3 sh -c true'
actual=$(cat "$CALL_LOG")
[ "$actual" = "$expected" ] || {
    printf 'expected: %s\nactual:   %s\n' "$expected" "$actual" >&2
    exit 1
}
