#!/usr/bin/env bash
# engine.sh — install the pinned decider engine (proplang-host) to $ENGINE_BIN.
#
#   scripts/engine.sh            # release asset if RELEASE_TAG is set, else build COMMIT
#
# The pin lives in config/engine.lock. A downloaded asset must match SHA256 or nothing is
# installed. Building from source needs ghc 9.10.3 + cabal on PATH (ghcup).
set -euo pipefail
root="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/.." && pwd)"
# shellcheck source=/dev/null
. "$root/config/engine.lock"
dest="${ENGINE_BIN:-$HOME/.local/bin/proplang-host}"
work="$(mktemp -d)"; trap 'rm -rf "$work"' EXIT

if [ -n "$RELEASE_TAG" ]; then
  gh release download "$RELEASE_TAG" -R "$REPO" -p "$ASSET" -D "$work"
  got="$(sha256sum "$work/$ASSET" | cut -c1-64)"
  if [ "$got" != "$SHA256" ]; then
    echo "error: $ASSET sha256 $got != pinned $SHA256 — not installed" >&2; exit 1
  fi
  src="$work/$ASSET"
else
  echo "no release pinned; building $REPO@$COMMIT from source" >&2
  git clone -q "https://github.com/$REPO.git" "$work/src"
  git -C "$work/src" checkout -q "$COMMIT"
  (cd "$work/src" && cabal build -v0 exe:proplang-host && cp "$(cabal list-bin proplang-host)" "$work/$ASSET")
  src="$work/$ASSET"
fi
install -D -m 0755 "$src" "$dest"
echo "installed $dest ($(sha256sum "$dest" | cut -c1-16)…)"
