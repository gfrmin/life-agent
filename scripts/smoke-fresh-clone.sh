#!/usr/bin/env bash
# smoke-fresh-clone.sh — prove a fresh checkout works end-to-end with NO second
# clone (pkm is in-tree), NO network, and NO API key: bootstrap the synthetic
# sample corpus and assert each synthetic fact retrieves to its own document.
#
# What this guarantees deterministically (no LLM, so no flakiness / no key):
#   1. pkm resolves from this repo's src/, not a sibling ../pkm  (monorepo merge).
#   2. The pipeline migrate→ingest→extract→chunk→rebuild-index→search works.
#   3. Provenance is clean: the OWNER's id (123456789) retrieves to identity.md
#      and the partner DECOY's id (987654321) retrieves to partner-charles.md —
#      never crossed. That separation is the substrate the synthesis-time
#      identity guard (owner.md) relies on; the guard itself is an LLM behaviour
#      exercised by the eval/dogfood, not here.
#
# Used by CI and runnable locally. It builds in a temp sandbox and never touches
# your real $LIFE_AGENT_KB.
set -euo pipefail

root="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/.." && pwd)"
sandbox="$(mktemp -d "${TMPDIR:-/tmp}/la-smoke.XXXXXX")"
cleanup() { rm -rf "$sandbox"; }
trap cleanup EXIT

# A fresh clone has no inherited KB/config env and no ../pkm to fall back on.
unset LIFE_AGENT_KB PKM_CONFIG
cfg="$sandbox/pkm.yaml"

fail() { echo "SMOKE FAIL: $*" >&2; exit 1; }

echo "== 0. pkm is in-tree (no sibling ../pkm needed) =="
pkm_file="$(uv run --project "$root" python -c 'import pkm, sys; sys.stdout.write(pkm.__file__)')"
# In-tree under this repo (not a sibling clone). The merge brought pkm into src/.
case "$pkm_file" in
  "$root"/*) echo "  pkm resolves in-tree from $pkm_file" ;;
  *) fail "pkm resolved from $pkm_file, outside this repo — monorepo merge regressed" ;;
esac
case "$pkm_file" in
  *pkm*) : ;;
  *) fail "unexpected pkm path $pkm_file" ;;
esac

echo "== 1. bootstrap the sample corpus =="
LIFE_AGENT_SAMPLE_DIR="$sandbox" "$root/scripts/bootstrap-sample.sh"

# search() prints "  N. [score] /path" lines; assert the TOP hit's path matches.
assert_top_hit() {
  local query="$1" expect="$2" out
  out="$(uv run --project "$root" pkm --config "$cfg" search "$query" --k 3)"
  local top
  top="$(printf '%s\n' "$out" | grep -E '^[[:space:]]*1\. ' || true)"
  echo "  search '$query' -> ${top:-<no results>}"
  printf '%s' "$top" | grep -q "$expect" || fail "top hit for '$query' was not $expect"
}

echo "== 2. provenance: each synthetic id retrieves to its OWN document =="
assert_top_hit "123456789" "identity.md"          # the owner's id
assert_top_hit "987654321" "partner-charles.md"   # the partner decoy's id — not crossed

echo "== 3. PII guard runs clean on the committed tree (shapes-only) =="
uv run --project "$root" python "$root/.githooks/pii_check.py" --shapes-only \
  || fail "pii_check flagged tracked content"

echo
echo "SMOKE PASS: fresh checkout builds the sample and answers with clean provenance."
