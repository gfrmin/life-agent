# Git hooks — structural PII guard

This is a **public** repo; personal data must never enter it (SPEC §14.9).
These version-controlled hooks block committing or pushing content shaped like
real personal data. Activate them once per clone:

    git config core.hooksPath .githooks

(Git ≥2.9. Scripts need the executable bit; if a clone dropped it, run
`chmod +x .githooks/pre-commit .githooks/pre-push`.)

`pii_check.py` enforces an **allowlist of safe shapes** (no checksum-valid
Israeli IDs, only `@example.*` emails, no passport/Israeli-mobile patterns)
plus a **private denylist** read from `$LIFE_AGENT_KB/pii-patterns.txt`, which
is never stored here. Export `LIFE_AGENT_KB` to point at your knowledge base;
without it the pre-commit/pre-push hooks **fail closed** (refuse to scan) — by
design. These hooks are the **whole gate** (no server-side CI, by choice for a
solo repo), so pre-push scans every blob in every pushed commit — not just the
net diff — and pre-commit catches leaks before they reach history.

```
python3 .githooks/pii_check.py                 # scan the whole tracked tree
python3 .githooks/pii_check.py --shapes-only    # CI mode, no private list
```

Exempt a reviewed false positive with an inline `PII-OK` marker on that line.
Synthetic fixtures are chosen to pass by construction: synthetic Israeli IDs are
deliberately checksum-invalid (e.g. `123456789`), synthetic emails use
`@example.*`.
