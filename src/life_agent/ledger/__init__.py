"""The unified ledger — one append-only event stream, every read-model a fold of it.

Design: ``docs/unified-ledger-design.md`` (adopted 2026-08-18). This package holds, in
tranche 1: the typed event schema (:mod:`.schema`); the per-source segment store with the
§10 durability contract (:mod:`.store`); the legacy paths object (:mod:`.paths`); the
per-source legacy parsers with the §2 envelope rules (:mod:`.sources`); the migration writer,
sweeps and two-route counts (:mod:`.migrate`); the §7 fold adapters — the existing folds over
the stream's records by materialisation (:mod:`.adapters`); and the golden-replay harness
(:mod:`.golden`) that snapshots every §9 artefact from the legacy stores with the *existing*
folds and compares the replay — from the legacy stores or, with ``--from stream``, from the
unified stream — by the pre-stated criteria; and the live mirror (:mod:`.mirror`, §8 C5) — the
one call each typed writer makes after its legacy append (append-shaped, loud when behind,
fail-open and counted, ``LIFE_AGENT_LEDGER_MIRROR=0`` the recorded rollback). The three swept
sources are synced by the manual CLI (``python -m life_agent.ledger.migrate sync all``); no
reader is cut over and no legacy store is retired in tranche 1.
"""
