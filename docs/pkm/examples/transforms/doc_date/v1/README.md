# doc_date — one primary date per document (SPEC §18.12)

Projects `{format_version: 1, date: "YYYY-MM-DD" | null}` from each artifact: the
document's OWN primary date (an email's Date header, an invoice's issue date), never the
ingestion time. `null` means no primary date is determinable — the indeterminate marker
that temporal consumers must NAME in answers, never silently drop.

Four declarations, two producer classes: `doc_date_email` is a deterministic stdlib
parse over the rendered email header block; `doc_date_{docling,pandoc,tesseract}` all
dispatch to the grammar-constrained local-model producer (the projection is a function
of content, not of which extractor produced it).

Install into a live root: copy `transforms/`, `prompts/`, `schemas/` contents into the
root's same-named directories. Materialisation is demand-driven — `pkm derive
doc_date_docling --input <artifact-key>` (or the ask path's `/derive`); there is no
eager sweep requirement.
