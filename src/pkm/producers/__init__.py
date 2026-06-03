"""Concrete producers for Phase 1.

Three extractors, imported one per file for now (SPEC §7.2):

  - ``pkm.producers.pandoc``        — fast baseline, common formats.
  - ``pkm.producers.docling``       — layout + tables.
  - ``pkm.producers.unstructured``  — email and odd formats.

No plugin system, no registry. Each producer is a concrete class
conforming to ``pkm.producer.Producer``. When a fourth producer
arrives, we'll consider abstraction (CLAUDE.md).
"""
