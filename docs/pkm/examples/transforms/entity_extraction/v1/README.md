# Entity extraction v1 — canonical transform files

This directory contains the canonical files for the entity extraction
transform at version 0.2.0. These are the source of truth: both test
fixtures and live root deployments should copy from here.

The files follow the SPEC v0.2.0 §19.1 directory layout. To deploy
to a live root, copy the five subdirectories (`transforms/`,
`prompts/`, `schemas/`, `policies/`) into the root directory and
add the policies section to `config.yaml`.

The prompt and schema survived Stage C's 10-category adversarial
pass without revision. The v1 suffix is immutable per Invariant 13:
if a revision is needed, create v2 files alongside.
