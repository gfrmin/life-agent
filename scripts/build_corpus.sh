#!/usr/bin/env bash
# build_corpus.sh — assemble the corpus from notes, already-extracted text, and OCR'd
# document images, into $LIFE_AGENT_KB/raw (outside the repo — see docs/kb-schema.md).
# Idempotent: only adds what's new. See docs/data-seams.md.
set -euo pipefail

# Knowledge/PII lives outside the repo, at $LIFE_AGENT_KB.
LIFE_AGENT_KB="${LIFE_AGENT_KB:-$HOME/.life-agent/kb}"
RAW="${RAW:-$LIFE_AGENT_KB/raw}"
NOTES_SRC="${NOTES_SRC:-$HOME/notes}"
PARSED_SRC="${PARSED_SRC:-$HOME/parsed}"
DOCS_SRC="${DOCS_SRC:-$HOME/documents}"
LANGS="${TESS_LANGS:-heb+eng}"

mkdir -p "$RAW/notes" "$RAW/parsed-text" "$RAW/ocr"
INDEX="$RAW/docs-index.tsv"
: > "$INDEX"

echo "[notes] symlinking *.md from $NOTES_SRC"
if [ -d "$NOTES_SRC" ]; then
  find "$NOTES_SRC" -type f -iname '*.md' -print0 | while IFS= read -r -d '' f; do
    base=$(printf '%s' "$f" | sed "s#^$NOTES_SRC/##; s#/#__#g")
    ln -sf "$f" "$RAW/notes/$base"
    printf 'note\t%s\t%s\n' "$RAW/notes/$base" "$f" >> "$INDEX"
  done
fi

echo "[parsed] copying extracted .txt from $PARSED_SRC"
if [ -d "$PARSED_SRC" ]; then
  find "$PARSED_SRC" -type f -iname '*.txt' -print0 | while IFS= read -r -d '' f; do
    cp -n "$f" "$RAW/parsed-text/$(basename "$f")" 2>/dev/null || true
    printf 'parsed\t%s\t%s\n' "$RAW/parsed-text/$(basename "$f")" "$f" >> "$INDEX"
  done
fi

echo "[ocr] OCR'ing document images from $DOCS_SRC (lang=$LANGS, cached)"
if [ -d "$DOCS_SRC" ]; then
  find "$DOCS_SRC" -type f -iregex '.*\.\(jpg\|jpeg\|png\|tif\|tiff\|bmp\)' -print0 \
    | xargs -0 -P 4 -I{} bash -c '
        src="$1"; rawocr="$2"; langs="$3"; index="$4"
        rel=$(printf "%s" "$src" | sed "s#/#__#g")
        out="$rawocr/${rel}.txt"
        if [ ! -s "$out" ] || [ "$src" -nt "$out" ]; then
          { printf "SOURCE: %s\n\n" "$src"; tesseract "$src" stdout -l "$langs" 2>/dev/null; } > "$out" || true
        fi
        printf "ocr\t%s\t%s\n" "$out" "$src" >> "$index"
      ' _ {} "$RAW/ocr" "$LANGS" "$INDEX"
fi

echo "done. corpus at $RAW"
wc -l "$INDEX" 2>/dev/null || true
