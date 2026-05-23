#!/usr/bin/env bash
# needle.sh — find any document across the corpus, including text *inside* scanned images.
#
#   scripts/needle.sh "תעודת זהות"      # Hebrew: identity card
#   scripts/needle.sh "teudat"           # transliteration / filename hits
#
# Strategy: filename matches, then content via rga (searches inside PDFs/office/text),
# then OCR (tesseract heb+eng, cached) for images and grep over that.
# Limitation: image-only (scanned) PDFs aren't OCR'd here — rasterise with pdftoppm first if needed.
set -euo pipefail

QUERY="${*:-}"
[ -z "$QUERY" ] && { echo "usage: $0 <query>"; exit 2; }

DOCS_DIR="${DOCS_DIR:-/mnt/yo/dropbox/documents}"
PARSED_DIR="${PARSED_DIR:-/mnt/yo/parsed}"
# Knowledge/PII lives outside the repo, at $LIFE_AGENT_KB (see docs/kb-schema.md).
LIFE_AGENT_KB="${LIFE_AGENT_KB:-$HOME/.life-agent/kb}"
OCR_CACHE="${OCR_CACHE:-$LIFE_AGENT_KB/ocr-cache}"
LANGS="${TESS_LANGS:-heb+eng}"
mkdir -p "$OCR_CACHE"

echo "== filename matches =="
find "$DOCS_DIR" -type f 2>/dev/null | rg -i -- "$QUERY" || true

echo
echo "== content matches (PDFs / office / text, via rga) =="
rga -i --no-messages -- "$QUERY" "$DOCS_DIR" "$PARSED_DIR" || true

echo
echo "== OCR'ing images (cached; first run is slow) =="
find "$DOCS_DIR" -type f -iregex '.*\.\(jpg\|jpeg\|png\|tif\|tiff\|bmp\)' -print0 2>/dev/null \
  | xargs -0 -P 4 -I{} bash -c '
      src="$1"; cache="$2"; langs="$3"
      key=$(printf "%s" "$src" | sha1sum | cut -c1-16)
      out="$cache/$key.txt"
      if [ ! -s "$out" ] || [ "$src" -nt "$out" ]; then
        { printf "SOURCE: %s\n" "$src"; tesseract "$src" stdout -l "$langs" 2>/dev/null; } > "$out" || true
      fi
    ' _ {} "$OCR_CACHE" "$LANGS"

echo
echo "== matches inside images (OCR text) =="
while IFS= read -r f; do
  src=$(head -n1 "$f" | sed 's/^SOURCE: //')
  echo "  $src"
  rg -i --no-filename --no-line-number -- "$QUERY" "$f" | sed 's/^/      /' | head -n 3
done < <(rg -il -- "$QUERY" "$OCR_CACHE" 2>/dev/null || true)
