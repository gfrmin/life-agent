"""Staleness — SPEC §18.10.

A read-only, deterministic view over the catalogue: which artifacts has a later
derivation already replaced, and which artifacts were built on top of those?

    superseded(conn) -> {old_cache_key: current_cache_key}
    stale(conn)      -> [StaleArtifact(...)]  sorted by cache_key

The cache is append-only (SPEC §6.2): re-deriving a source with a newer producer
version writes a new artifact beside the old one. *Current* (§18.10) is the most
recently produced success in each ``(input_hash, producer_name)`` group — §18.1's
recency rule applied within a group, with ``cache_key`` as the deterministic
tiebreak. *Superseded* are the non-current members. *Stale* is the superseded set
closed downstream over ``artifact_lineage``. This module only reads: it never
writes, never deletes, never touches the filesystem (flag-never-delete).
"""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import duckdb

# A stale artifact's reason takes one of these two values.
SUPERSEDED = "superseded"      # a newer success for the same (input_hash, producer)
STALE_INPUT = "stale-input"    # derived (transitively) from a stale artifact


@dataclass(frozen=True)
class StaleArtifact:
    """One stale artifact and why it is stale.

    ``via`` is the current cache_key that supersedes it (when ``reason`` is
    ``SUPERSEDED``) or the nearest stale upstream artifact through which it was
    reached (when ``reason`` is ``STALE_INPUT``).
    """

    cache_key: str
    producer_name: str
    reason: str
    via: str


def superseded(conn: duckdb.DuckDBPyConnection) -> dict[str, str]:
    """Map each superseded cache_key to the current key that supersedes it.

    Within each ``(input_hash, producer_name)`` group restricted to
    ``status='success'``, the current artifact is the most recently produced
    (``produced_at`` then ``cache_key`` as a deterministic tiebreak); every other
    member of the group is superseded by it. A group of one yields nothing.
    """
    rows = conn.execute(
        "SELECT cache_key, input_hash, producer_name, produced_at "
        "FROM artifacts WHERE status = 'success'"
    ).fetchall()

    groups: dict[tuple[str, str], list[tuple[object, str]]] = defaultdict(list)
    for cache_key, input_hash, producer_name, produced_at in rows:
        groups[(input_hash, producer_name)].append((produced_at, cache_key))

    result: dict[str, str] = {}
    for members in groups.values():
        if len(members) < 2:
            continue
        # most-recent-first; (produced_at, cache_key) is a total deterministic order
        members.sort(key=lambda m: (m[0], m[1]), reverse=True)
        current = members[0][1]
        for _, key in members[1:]:
            result[key] = current
    return result


def stale(conn: duckdb.DuckDBPyConnection) -> list[StaleArtifact]:
    """All stale artifacts: the superseded set plus its downstream lineage closure.

    Superseded artifacts are reported with reason ``SUPERSEDED``; everything
    reachable downstream of a stale artifact (via ``artifact_lineage``, following
    edges where the stale artifact is the ``input_cache_key``) that is not itself
    superseded is reported with reason ``STALE_INPUT``. ``SUPERSEDED`` takes
    precedence — a directly-replaced artifact keeps that reason even if it also
    sits downstream of another stale artifact. The result is sorted by cache_key.
    """
    superseded_map = superseded(conn)
    producer_of = dict(
        conn.execute("SELECT cache_key, producer_name FROM artifacts").fetchall()
    )

    # Downstream adjacency: input_cache_key -> [dependent artifact_cache_key, ...].
    downstream: dict[str, list[str]] = defaultdict(list)
    for artifact_key, input_key in conn.execute(
        "SELECT artifact_cache_key, input_cache_key FROM artifact_lineage"
    ).fetchall():
        downstream[input_key].append(artifact_key)

    found: dict[str, StaleArtifact] = {}
    for key, current in superseded_map.items():
        found[key] = StaleArtifact(key, producer_of.get(key, ""), SUPERSEDED, current)

    # BFS the downstream closure from the superseded roots. Sorted frontier +
    # sorted adjacency make ``via`` (the nearest stale ancestor reached first)
    # deterministic.
    queue: deque[str] = deque(sorted(superseded_map))
    while queue:
        upstream = queue.popleft()
        for dependent in sorted(downstream.get(upstream, ())):
            if dependent in found:
                continue  # already stale (keeps SUPERSEDED precedence, avoids cycles)
            found[dependent] = StaleArtifact(
                dependent, producer_of.get(dependent, ""), STALE_INPUT, upstream
            )
            queue.append(dependent)

    return [found[key] for key in sorted(found)]
