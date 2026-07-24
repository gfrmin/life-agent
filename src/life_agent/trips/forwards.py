"""Resolve a forwarded booking mail back to the original it forwarded, before extraction.

Design-mandated (docs/trips-design.md §Ingest): resolution doubles corpus yield (39->80
reservations) and is the sole recovery path for pre-2018 history. Pure logic — the notmuch
``id:``/``subject:`` lookups are injected, so this is socket-free and fully unit-tested.
Precedence, first that resolves to an existing, different message wins:
X-Forwarded-Message-Id -> In-Reply-To -> last References id -> subject match (prefixes stripped).
"""
from __future__ import annotations

import re
from collections.abc import Callable, Mapping

# Forwarding / reply subject prefixes across the clients in a 15-year corpus (en/fr/de/nl...).
_PREFIX_RE = re.compile(
    r"^\s*(?:(?:re|fwd?|tr|wg|rv|sv|vs|aw|antw)\s*:\s*)+", re.IGNORECASE
)


def _clean_id(raw: str) -> str:
    """Strip surrounding <> and whitespace from a Message-ID header value."""
    return raw.strip().strip("<>").strip()


def _strip_prefixes(subject: str) -> str:
    return _PREFIX_RE.sub("", subject).strip()


def _references_last(value: str) -> str | None:
    ids = re.findall(r"<[^>]+>", value)
    return _clean_id(ids[-1]) if ids else None


def resolve_original(
    headers: Mapping[str, str],
    lookup: Callable[[str], list[str]],
) -> str | None:
    """Return the msgid this forward forwarded, or ``None`` if unresolved.

    ``lookup(query)`` runs a notmuch query and returns matching msgids — injected so this stays
    pure. The forward's own Message-ID is never returned as its 'original'.
    """
    own = _clean_id(headers.get("Message-ID", ""))

    queries: list[str] = []
    if xfwd := headers.get("X-Forwarded-Message-Id"):
        queries.append(f"id:{_clean_id(xfwd)}")
    if irt := headers.get("In-Reply-To"):
        queries.append(f"id:{_clean_id(irt)}")
    if (refs := headers.get("References")) and (last := _references_last(refs)):
        queries.append(f"id:{last}")

    for query in queries:
        for mid in lookup(query):
            if mid and mid != own:
                return mid

    subject = headers.get("Subject")
    if subject:
        stripped = _strip_prefixes(subject)
        # Only search when the subject ACTUALLY carried a forwarding prefix — otherwise a plain
        # booking would trigger a broad subject match against unrelated mail.
        if stripped and stripped != subject.strip():
            for mid in lookup(f'subject:"{stripped}"'):
                if mid and mid != own:
                    return mid
    return None
