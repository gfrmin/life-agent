# SPEC-PRINCIPLES — PKM foundational principles

This is a stable, cross-version document. Numbered SPECs (`SPEC-v0.2.0.md`, `SPEC-v0.3.0.md`, …)
reference it but do not redefine it. It is not phase-scoped; it applies to PKM as a whole.

**§1. Sources.** A source is bytes that exist independently of PKM. Its identity is `sha256` of those
bytes. The `source_id` of any source must be reproducible by running `sha256sum` on the raw bytes
outside of PKM. If computing a source's identity requires running PKM code, the artefact is not a
source — it is a derivation, and belongs in the transform layer.

**§2. Events.** A transform invocation is an event. Its identity is the hash of its inputs (the
source/derivation identities it consumed, the producer, and the producer's configuration — including
model version, SDK version, prompt template hash, output schema hash, and any other input that
defines what the event *is*). Its output is what it produced.

**§3. Recording.** The system records events: which happened, and what they produced. The cache is a
view over this record, optimised for the query "given these inputs, has this event happened, and if
so what was the output?"

**§4. Truth is empirical.** Records make no claim to truth. They are observations under conditions,
and their reliability is an empirical, ongoing question — to be assessed by downstream reasoning, not
by the recording layer.

## Diagnostics (one-question tests)

**Source or derivation?** *Could this artefact exist if PKM were deleted?* If yes, source. If no,
derivation. There is no third category.

**What goes in the event tuple?** *If this thing changed, would I want it to count as a different
event?* If yes, include it. If no, exclude it. (Note: this is an ontological choice about what
equivalence the system recognises, not a fact about reproducibility.)

**Is this a cache concern or a trust concern?** *Am I asking "did this happen?" or "was the answer
correct?"* The first is the cache's job; the second is downstream reasoning's job. Do not conflate
them.

## Implications worth stating

**Reproducibility is a per-producer property, declared, not assumed.** A producer may be
bit-reproducible, reproducible-in-distribution, or non-reproducible. The system records what happened
regardless; consumers that need reproducibility query for it.

**Normalization is a derivation, not a source.** When bytes need interpretation, cleaning, or
canonicalization before downstream use (quote-stripping emails, OCR'ing images, resolving Matrix
mentions), the interpretation is performed by a producer. The raw bytes remain the source, always.

**`sha256` is the canonical hash.** Reserved for future multihash migration via a prefix
(`sha256:...`) but not currently varied.
