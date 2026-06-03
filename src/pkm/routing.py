"""Routing (SPEC §7.3) — which producers run on a given source.

A single pure function. Not a rule engine, not configuration. Given
the source's extension, tags, and the set of producers already
attempted (with their outcomes), returns the ordered list of
producers that should still run. When every applicable producer
has either succeeded or been retried to exhaustion, the return is
``[]`` — which is how ``pkm extract`` achieves idempotency against
already-extracted sources.

Policy per SPEC §7.3 at v0.1.6:

  1. Pandoc on every source whose extension Pandoc handles.
  2. Docling on PDFs (format-based eager), on any Docling-handled
     source tagged as layout-sensitive (``invoice``, ``report``,
     ``contract``), and as a fallback when Pandoc failed on a
     Docling-handled source.
  3. Unstructured on ``.msg`` email (format-based eager) and as the
     catch-all when every other applicable producer is blocked —
     either it does not handle the format or it already failed. This
     collapses two SPEC cases (nobody else handles, both-others-failed)
     into one predicate.
  4. Email on ``.eml`` (format-based eager) via a dedicated stdlib
     producer — the only producer for ``.eml``, no fallback (§7.3
     rule 5). ``.eml`` moved off Unstructured in v0.5.0.

The router reads ``handled_formats`` class attributes on the
concrete producers; it does NOT construct them. The version check
and model loading that constructors perform are paid only once per
CLI invocation, by the caller in ``pkm.extract``.
"""

from __future__ import annotations

from collections.abc import Collection

from pkm.producers.docling import DoclingProducer
from pkm.producers.email_producer import EmailProducer
from pkm.producers.pandoc import PandocProducer
from pkm.producers.tesseract import TesseractProducer
from pkm.producers.unstructured import UnstructuredProducer

_LAYOUT_SENSITIVE_TAGS: frozenset[str] = frozenset(
    {"invoice", "report", "contract"}
)
"""User tags that escalate a Docling-handled source through Docling
even when it's not a PDF. Tags are optional modulators; format
signals remain the default (SPEC §7.3 rationale)."""

_EAGER_DOCLING_EXTENSIONS: frozenset[str] = frozenset({".pdf"})
"""Extensions that trigger Docling unconditionally. PDF is the
canonical layout-heavy format and tag coverage would be unreliable;
the format-based trigger ensures every PDF gets Docling's
structured extraction regardless of tagging diligence."""

_EAGER_UNSTRUCTURED_EXTENSIONS: frozenset[str] = frozenset({".msg"})
"""Email formats that trigger Unstructured unconditionally. ``.eml`` moved to
the dedicated ``email`` producer in v0.5.0; ``.msg`` (Outlook OLE) stays here
because the stdlib ``email`` module cannot parse it."""


def route(
    *,
    extension: str,
    tags: Collection[str] = (),
    succeeded: Collection[str] = (),
    failed: Collection[str] = (),
    empty_succeeded: Collection[str] = (),
    retry_failed: bool = False,
) -> list[str]:
    """Return the ordered list of producer names to run.

    Args:
        extension: The source's file extension including the dot,
            e.g. ``".pdf"``. Matched case-insensitively.
        tags: User-applied tags on the source (from ``sources.yaml``
            and the ``source_tags`` table).
        succeeded: Producer names that already have a successful
            artifact for this source. Always excluded from the
            returned list.
        failed: Producer names that already have a failed artifact
            for this source. Excluded unless ``retry_failed``.
        empty_succeeded: Producer names whose artifact succeeded but
            extracted no text (e.g. Docling on an image-only PDF).
            The producer is NOT re-run (its artifact is valid), but
            its empty result unlocks fallback producers. Currently:
            if ``"docling"`` is in ``empty_succeeded`` and extension
            is ``.pdf``, Tesseract is added as a fallback via
            ``pdftoppm`` rasterization (SPEC v0.3.1 §7.3).
        retry_failed: If True, include previously-failed producers
            in the candidate set (wired from ``pkm extract
            --retry-failed``).

    Returns:
        Ordered list of producer names (``"pandoc"``, ``"docling"``,
        ``"unstructured"``, ``"tesseract"``). Empty when every
        applicable producer has succeeded or no producer applies.
    """
    ext = extension.lower()
    tag_set = set(tags)
    succeeded_set = set(succeeded)
    failed_set = set(failed)
    empty_succeeded_set = set(empty_succeeded)

    plan: set[str] = set()

    # 1. Pandoc: baseline on every source it handles.
    if ext in PandocProducer.handled_formats:
        plan.add("pandoc")

    # 2. Docling: eager on PDFs + layout-tagged, fallback on
    #    Pandoc-failed.
    if ext in DoclingProducer.handled_formats:
        eager = (
            ext in _EAGER_DOCLING_EXTENSIONS
            or bool(tag_set & _LAYOUT_SENSITIVE_TAGS)
        )
        fallback = "pandoc" in failed_set
        if eager or fallback:
            plan.add("docling")

    # 3. Unstructured: eager on email; otherwise runs when every
    #    earlier producer is blocked. "Blocked" means the producer
    #    is not going to attempt this source: either it's not in
    #    the plan (doesn't handle the format, or handles but wasn't
    #    triggered) or it's already failed. This collapses §7.3's
    #    "nobody-else-handles" and "both-others-failed" cases into
    #    one predicate, and crucially also covers the "handles but
    #    the eager/fallback triggers didn't fire" case — a .pptx
    #    that Docling technically handles but routing didn't
    #    escalate to.
    if ext in UnstructuredProducer.handled_formats:
        eager = ext in _EAGER_UNSTRUCTURED_EXTENSIONS
        pandoc_blocked = "pandoc" not in plan or "pandoc" in failed_set
        docling_blocked = "docling" not in plan or "docling" in failed_set
        if eager or (pandoc_blocked and docling_blocked):
            plan.add("unstructured")

    # 4. Tesseract:
    #    - Eager on image formats (non-PDF entries in handled_formats).
    #    - Fallback-only on PDFs: only when Docling is in empty_succeeded
    #      (image-only PDF detected via pdftoppm rasterization path).
    #    Note: .pdf IS in TesseractProducer.handled_formats so that
    #    _needed_producer_names constructs the producer for PDF corpora,
    #    but routing does NOT add it eagerly — only via empty_succeeded.
    #    (SPEC v0.3.1 §7.3)
    _tesseract_image_formats = TesseractProducer.handled_formats - {".pdf"}
    if ext in _tesseract_image_formats or (
        ext == ".pdf" and "docling" in empty_succeeded_set
    ):
        plan.add("tesseract")

    # 5. Email: dedicated stdlib RFC822 producer, eager and exclusive on
    #    `.eml` (its only handled format, so handled_formats IS the trigger —
    #    no separate eager set). No fallback to or from Unstructured: a
    #    malformed `.eml` is a recorded failure, not handed to the producer
    #    that stalls on large MIME (SPEC §7.3 rule 5).
    if ext in EmailProducer.handled_formats:
        plan.add("email")

    # Any previously-failed producer that handles the extension is a
    # retry candidate. Include in the plan; the filter below decides
    # whether to actually return it.
    for name, cls in (
        ("pandoc", PandocProducer),
        ("docling", DoclingProducer),
        ("unstructured", UnstructuredProducer),
        ("tesseract", TesseractProducer),
        ("email", EmailProducer),
    ):
        if name in failed_set and ext in cls.handled_formats:
            plan.add(name)

    ordered = [
        n
        for n in ("pandoc", "docling", "unstructured", "tesseract", "email")
        if n in plan
    ]

    result: list[str] = []
    for name in ordered:
        if name in succeeded_set:
            continue
        if name in failed_set and not retry_failed:
            continue
        result.append(name)
    return result
