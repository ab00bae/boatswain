#!/usr/bin/env bash
# Generates a report from a saved payload and asserts on every number, so the
# demo needs no token, no network, and produces the same output on every
# machine. Exits non-zero if any check fails.
#
#   ./demo.sh

set -uo pipefail
cd "$(dirname "$0")"

FIXTURE="data/sample-issues.json"
REPO="fastapi/typer"
# Pinned so the counts below are stable forever; the report is otherwise
# relative to the current date.
AS_OF="2026-08-15T12:00:00Z"
OUT=".demo-report.md"

if [ -t 1 ]; then
  GREEN=$'\033[32m'; RED=$'\033[31m'; BOLD=$'\033[1m'; DIM=$'\033[2m'; RESET=$'\033[0m'
else
  GREEN=''; RED=''; BOLD=''; DIM=''; RESET=''
fi

if [ -x ".venv/Scripts/python.exe" ]; then
  PY=".venv/Scripts/python.exe"
elif [ -x ".venv/bin/python" ]; then
  PY=".venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
  PY="python3"
else
  PY="python"
fi

pass=0
fail=0

cleanup() { rm -f "$OUT"; }
trap cleanup EXIT

section() { printf "\n${BOLD}%s${RESET}\n" "$1"; }

record() {
  if [ "$1" = "1" ]; then
    printf "  ${GREEN}PASS${RESET}  %s\n" "$2"
    pass=$((pass + 1))
  else
    printf "  ${RED}FAIL${RESET}  %s\n" "$2"
    [ -n "${3:-}" ] && printf "        ${DIM}%s${RESET}\n" "$3"
    fail=$((fail + 1))
  fi
}

expect_eq() {
  if [ "$1" = "$2" ]; then record 1 "$3"; else record 0 "$3" "expected '$1', got '$2'"; fi
}

# Pull one "| Label | value |" row out of the generated markdown.
metric() {
  sed -n "s/^| $1 | \(.*\) |$/\1/p" "$OUT" | head -1
}

contains() {
  if grep -qF "$1" "$OUT"; then record 1 "$2"; else record 0 "$2" "not found in report: $1"; fi
}

printf "${BOLD}boatswain demo${RESET}\n"
printf "${DIM}python: %s   fixture: %s   as of: %s${RESET}\n" "$PY" "$FIXTURE" "$AS_OF"

section "Generating a report from saved data"
"$PY" -m boatswain report --repo "$REPO" --fixture "$FIXTURE" \
  --now "$AS_OF" --sprint-days 14 --out "$OUT" >/dev/null 2>&1
expect_eq "0" "$?" "boatswain report exits successfully"
if [ -f "$OUT" ]; then record 1 "a markdown report was written"; else record 0 "a markdown report was written"; fi

section "Issues and pull requests are counted separately"
expect_eq "13" "$(metric 'PRs opened')" "13 pull requests opened in the window"
expect_eq "0" "$(metric 'Issues opened')" "0 issues opened — PRs are not miscounted as issues"
expect_eq "1" "$(metric 'Issues still open')" "1 issue still open"
expect_eq "40" "$(metric 'PRs still open')" "40 pull requests still open"

section "Pull request outcomes"
expect_eq "14" "$(metric 'PRs merged')" "14 pull requests merged"
expect_eq "2" "$(metric 'PRs closed unmerged')" "2 closed without merging"
expect_eq "88%" "$(metric 'Merge rate')" "merge rate is 88% of decided pull requests"

section "Stale detection reaches outside the window"
contains "678" "the year-old open issue is surfaced"
contains "364d" "its idle time is reported"
contains "## Stale issues" "stale issues get their own section"

section "Unicode survives the round trip"
contains "🚀" "emoji in an issue title is preserved"
contains "→" "the arrow in the window header is preserved"

section "Failure modes"
"$PY" -m boatswain report --repo "$REPO" --fixture missing.json >/dev/null 2>&1
expect_eq "2" "$?" "a missing fixture exits with code 2"
"$PY" -m boatswain report --repo "$REPO" --fixture "$FIXTURE" --now "not-a-date" >/dev/null 2>&1
expect_eq "2" "$?" "an unparseable --now exits with code 2"

total=$((pass + fail))
printf "\n${BOLD}%s${RESET}\n" "Summary"
printf "  %d/%d checks passed\n" "$pass" "$total"

if [ "$fail" -gt 0 ]; then
  printf "  ${RED}%d failed${RESET}\n\n" "$fail"
  exit 1
fi

printf "  ${GREEN}all checks passed${RESET}\n\n"
