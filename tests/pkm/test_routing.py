"""Tests for ``pkm.routing`` — the single-function Phase 1 router
(SPEC §7.3 at v0.1.6).

These tests pin the policy in concrete cases rather than
re-deriving it from code. If the policy changes, these tests must
be updated alongside SPEC §7.3 — they are the machine-checkable
form of the written rule.
"""

from __future__ import annotations

from pkm.routing import route

# --- Baseline: the common single-producer cases -------------------------


def test_markdown_with_no_tags_runs_pandoc_only() -> None:
    assert route(extension=".md", tags=[]) == ["pandoc"]


def test_docx_with_no_tags_runs_pandoc_only() -> None:
    """Docling also handles .docx, but routing keeps the baseline
    tight: Pandoc first, Docling only on failure / tag / PDF."""
    assert route(extension=".docx", tags=[]) == ["pandoc"]


def test_html_with_no_tags_runs_pandoc_only() -> None:
    assert route(extension=".html", tags=[]) == ["pandoc"]


# --- PDFs: format-based eager Docling ------------------------------------


def test_pdf_with_no_tags_runs_docling_eagerly() -> None:
    """Pandoc does not handle .pdf at all. Docling fires eagerly
    on format (§7.3). Unstructured does not run — Docling hasn't
    failed."""
    assert route(extension=".pdf", tags=[]) == ["docling"]


def test_pdf_with_layout_sensitive_tag_also_only_runs_docling() -> None:
    """A layout-sensitive tag on a PDF is redundant — the format
    already triggered Docling. The policy doesn't double-fire."""
    assert route(extension=".pdf", tags=["invoice"]) == ["docling"]


def test_pdf_where_docling_succeeded_is_a_no_op() -> None:
    assert route(extension=".pdf", succeeded=["docling"]) == []


def test_pdf_where_docling_failed_escalates_to_unstructured() -> None:
    """Docling failed, Pandoc does not apply. Unstructured is the
    only remaining applicable producer."""
    assert route(
        extension=".pdf", failed=["docling"]
    ) == ["unstructured"]


def test_pdf_where_docling_failed_with_retry_reruns_docling_too() -> None:
    assert route(
        extension=".pdf", failed=["docling"], retry_failed=True
    ) == ["docling", "unstructured"]


# --- Layout-sensitive tags escalate non-PDF --------------------------------


def test_md_tagged_invoice_escalates_to_docling() -> None:
    """A .md tagged ``invoice`` pushes both Pandoc (baseline) and
    Docling (tag-triggered escalation) into the plan."""
    assert route(extension=".md", tags=["invoice"]) == [
        "pandoc",
        "docling",
    ]


def test_docx_tagged_report_escalates_to_docling() -> None:
    assert route(extension=".docx", tags=["report"]) == [
        "pandoc",
        "docling",
    ]


def test_docx_tagged_contract_escalates_to_docling() -> None:
    assert route(extension=".docx", tags=["contract"]) == [
        "pandoc",
        "docling",
    ]


def test_untagged_docx_does_not_escalate() -> None:
    """Only layout-sensitive tags escalate. An arbitrary tag does
    not. This pins the whitelist behaviour."""
    assert route(extension=".docx", tags=["career", "cv"]) == ["pandoc"]


# --- Email formats: format-based eager Unstructured ----------------------


def test_eml_runs_email_producer_only() -> None:
    """v0.5.0: .eml routes to the dedicated `email` producer, NOT
    unstructured. It is the only producer for .eml."""
    assert route(extension=".eml", tags=[]) == ["email"]


def test_eml_does_not_route_to_unstructured() -> None:
    """No email→unstructured fallback: even with everything else
    blocked/failed, .eml never reaches unstructured."""
    plan = route(extension=".eml", failed=["email"], retry_failed=False)
    assert "unstructured" not in plan
    # and with retry, only email comes back
    assert route(extension=".eml", failed=["email"], retry_failed=True) == ["email"]


def test_msg_runs_unstructured_only() -> None:
    """.msg (Outlook OLE) stays with unstructured — stdlib can't parse it."""
    assert route(extension=".msg", tags=[]) == ["unstructured"]


# --- Fallback chain: failures cascade ------------------------------------


def test_md_where_pandoc_failed_escalates_to_docling_as_fallback() -> None:
    """Pandoc failed on a .md — Docling runs as fallback even
    though the .md isn't layout-sensitive. The filter drops
    pandoc (failed + no retry); Docling remains."""
    assert route(extension=".md", failed=["pandoc"]) == ["docling"]


def test_md_where_pandoc_and_docling_failed_escalates_to_unstructured() -> None:
    assert route(
        extension=".md", failed=["pandoc", "docling"]
    ) == ["unstructured"]


def test_docx_where_pandoc_failed_escalates_to_docling_as_fallback() -> None:
    assert route(extension=".docx", failed=["pandoc"]) == ["docling"]


def test_all_three_failed_with_retry_reruns_all() -> None:
    """All three producers have failed on a .md (imaginable only
    if a previous invocation reached them via the fallback chain).
    With --retry-failed, all three come back."""
    assert route(
        extension=".md",
        failed=["pandoc", "docling", "unstructured"],
        retry_failed=True,
    ) == ["pandoc", "docling", "unstructured"]


def test_all_three_failed_without_retry_returns_empty() -> None:
    assert (
        route(
            extension=".md",
            failed=["pandoc", "docling", "unstructured"],
        )
        == []
    )


# --- Long-tail formats: Unstructured as catch-all -------------------------


def test_doc_is_routed_to_unstructured_only() -> None:
    """Legacy .doc: Pandoc only reads .docx, Docling doesn't list
    .doc in its handled set. Unstructured claims .doc support and
    runs as the catch-all."""
    assert route(extension=".doc", tags=[]) == ["unstructured"]


def test_pptx_is_routed_to_unstructured_only() -> None:
    """Pandoc: no. Docling: no. Unstructured: yes."""
    assert route(extension=".pptx", tags=[]) == ["unstructured"]


def test_eml_with_email_succeeded_is_a_no_op() -> None:
    assert route(extension=".eml", succeeded=["email"]) == []


def test_eml_with_legacy_unstructured_artifact_still_routes_to_email() -> None:
    """A pre-v0.5.0 .eml extracted by unstructured does not block the new
    `email` producer — email isn't in `succeeded`, so it still runs (the
    rollout re-extracts via email and cleans up the orphan unstructured one)."""
    assert route(extension=".eml", succeeded=["unstructured"]) == ["email"]


def test_pptx_with_unstructured_failed_no_retry_returns_empty() -> None:
    """Nothing else to try — Pandoc and Docling don't handle .pptx.
    Without retry_failed, the result is empty and the catalogue
    records the failed attempt permanently."""
    assert (
        route(extension=".pptx", failed=["unstructured"]) == []
    )


def test_pptx_with_unstructured_failed_with_retry_reruns() -> None:
    assert route(
        extension=".pptx", failed=["unstructured"], retry_failed=True
    ) == ["unstructured"]


# --- Unknown formats and case sensitivity --------------------------------


def test_unknown_extension_returns_empty() -> None:
    """An extension no producer handles routes to nothing. Extract
    records nothing; the source appears in sources but produces no
    artifacts. Future producers might take it on; the catalogue
    remembers the source either way (via ingest)."""
    assert route(extension=".xyz", tags=[]) == []


def test_extension_matching_is_case_insensitive() -> None:
    """Source paths in the wild may come as .PDF, .DOCX, etc.
    Routing normalises to lowercase before matching."""
    assert route(extension=".PDF") == ["docling"]
    assert route(extension=".EmL") == ["email"]


# --- Idempotency invariant ------------------------------------------------


def test_re_running_with_all_successes_returns_empty() -> None:
    """The core idempotency property — once every applicable
    producer has succeeded, routing returns []."""
    assert (
        route(
            extension=".md",
            tags=["invoice"],
            succeeded=["pandoc", "docling"],
        )
        == []
    )


def test_partial_completion_returns_remainder() -> None:
    """Pandoc done, Docling pending (because tag escalates)."""
    assert (
        route(
            extension=".md",
            tags=["invoice"],
            succeeded=["pandoc"],
        )
        == ["docling"]
    )


# --- Retry semantics -----------------------------------------------------


def test_retry_failed_does_not_resurrect_succeeded() -> None:
    """retry_failed re-includes failures, but successes are
    never re-run by routing (cache invalidation is producer-
    version-bump territory, SPEC §14.5)."""
    assert (
        route(
            extension=".md",
            succeeded=["pandoc"],
            failed=["docling"],
            retry_failed=True,
        )
        == ["docling"]
    )


def test_layout_sensitive_tags_are_case_sensitive_lowercase() -> None:
    """The layout-sensitive tag whitelist is {invoice, report,
    contract} verbatim. 'Invoice' or 'INVOICE' do not match. This
    pins the exact contract with §7.3; if the user wants tag
    normalisation, that's an ingest-layer change, not routing."""
    assert route(extension=".md", tags=["Invoice"]) == ["pandoc"]
    assert route(extension=".md", tags=["INVOICE"]) == ["pandoc"]
    assert route(extension=".md", tags=["invoice"]) == [
        "pandoc",
        "docling",
    ]


# --- empty_succeeded routing (SPEC v0.3.1 §7.3) --------------------------


def test_pdf_tesseract_fallback_on_empty_docling() -> None:
    """PDF + docling in empty_succeeded → tesseract added, docling not re-run."""
    result = route(extension=".pdf", succeeded=["docling"], empty_succeeded=["docling"])
    assert "tesseract" in result
    assert "docling" not in result  # already succeeded, not re-run


def test_pdf_no_tesseract_when_docling_has_text() -> None:
    """PDF + docling in succeeded (with text) → no tesseract fallback."""
    result = route(extension=".pdf", succeeded=["docling"])
    assert "tesseract" not in result


def test_pdf_tesseract_fallback_docling_not_re_run_when_in_succeeded() -> None:
    """Docling stays excluded when in succeeded; empty_succeeded unlocks Tesseract."""
    result = route(extension=".pdf", succeeded=["docling"], empty_succeeded=["docling"])
    assert "tesseract" in result
    assert "docling" not in result  # already in succeeded, routing suppresses it


def test_pdf_empty_succeeded_when_docling_already_attempted_and_empty() -> None:
    """The typical runtime case: docling in succeeded AND empty_succeeded."""
    result = route(
        extension=".pdf",
        succeeded=["docling"],
        empty_succeeded=["docling"],
    )
    assert "tesseract" in result
    assert "docling" not in result


def test_empty_succeeded_no_effect_on_non_pdf() -> None:
    """empty_succeeded for docling only unlocks Tesseract on PDFs, not images."""
    result = route(extension=".png", empty_succeeded=["docling"])
    assert "tesseract" in result  # .png always triggers Tesseract (image)
    # No extra effect from empty_succeeded — same result as without it
    result_baseline = route(extension=".png")
    assert result == result_baseline


# --- The producers satisfy the Protocol extension ------------------------


def test_all_three_producers_have_handled_formats_class_attribute() -> None:
    """Routing reads ``handled_formats`` off the class (no
    construction). This test verifies the attribute is present on
    each producer class, is a frozenset, and contains at least one
    extension formatted as ``.ext`` (dot-prefixed, lowercase)."""
    from pkm.producers.docling import DoclingProducer
    from pkm.producers.pandoc import PandocProducer
    from pkm.producers.unstructured import UnstructuredProducer

    for cls in (PandocProducer, DoclingProducer, UnstructuredProducer):
        hf = cls.handled_formats
        assert isinstance(hf, frozenset)
        assert hf, f"{cls.__name__}.handled_formats is empty"
        for ext in hf:
            assert ext.startswith(".")
            assert ext == ext.lower()
