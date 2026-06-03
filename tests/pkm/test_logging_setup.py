"""Tests for ``pkm.logging_setup`` — JSONL logging (SPEC §10).

Per the Step 7b design: one comprehensive test is enough. The test
invokes a real wired CLI command (``pkm migrate`` — simplest, no
fixtures), then asserts the infrastructure worked:

  - the expected JSONL file exists at ``<root>/logs/<today>.jsonl``;
  - every line parses as JSON;
  - at least one line carries a recognisable structured event
    (``migration_applied``) with the required fields in the
    required formats (timestamp is ISO 8601 with explicit UTC
    offset; level is one of the declared values; component is a
    ``pkm.*`` dotted path; event is present; message is a string).

Not in scope: exhaustive per-event coverage (that belongs on each
caller's own tests), log rotation (not implemented in Phase 1), or
cross-process file sharing.
"""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path

import pytest

from pkm.cli import main


def test_migrate_writes_jsonl_log_file_with_expected_shape(
    tmp_root: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(f"root_dir: {tmp_root}\n", encoding="utf-8")

    rc = main(["--config", str(cfg_path), "migrate"])
    assert rc == 0
    capsys.readouterr()

    log_file = tmp_root / "logs" / f"{date.today().isoformat()}.jsonl"
    assert log_file.exists(), f"expected {log_file} after migrate"

    lines = log_file.read_text(encoding="utf-8").splitlines()
    assert lines, "log file is empty"

    records = [json.loads(line) for line in lines]

    applied = [r for r in records if r.get("event") == "migration_applied"]
    assert applied, (
        f"no migration_applied events in {log_file}; "
        f"got events: {sorted({r.get('event') for r in records})}"
    )

    record = applied[0]
    for field in ("timestamp", "level", "component", "event", "message"):
        assert field in record, f"{field!r} missing from {record!r}"

    # Timestamp: ISO 8601 with explicit UTC offset.
    assert record["timestamp"].endswith("+00:00"), record["timestamp"]
    datetime.fromisoformat(record["timestamp"])  # raises on malformed

    # Level is one of the declared values (no CRITICAL).
    assert record["level"] in {"DEBUG", "INFO", "WARNING", "ERROR"}

    # Component is a pkm.* dotted path.
    assert record["component"].startswith("pkm."), record["component"]

    # Event-specific fields from extra= survive into the record.
    assert "schema_version" in record
    assert "migration_id" in record

    assert isinstance(record["message"], str)


def test_fixed_field_order_in_jsonl_output(
    tmp_root: Path, tmp_path: Path,
) -> None:
    """Field order in the emitted JSON is fixed per SPEC §10 design:
    identifying fields come first (timestamp, level, component,
    event), then event-specific fields from ``extra=``, then
    ``message`` last. Readers scanning top-to-bottom benefit; the
    whole point of structured logging is undercut if ``message``
    (often the longest field) crowds the identifiers.
    """
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(f"root_dir: {tmp_root}\n", encoding="utf-8")
    main(["--config", str(cfg_path), "migrate"])

    log_file = tmp_root / "logs" / f"{date.today().isoformat()}.jsonl"
    first_line = log_file.read_text(encoding="utf-8").splitlines()[0]

    # json.loads into dict preserves insertion order (Python 3.7+),
    # which is what the formatter emits. Assert the fixed prefix and
    # the fact that message is last.
    parsed = json.loads(first_line)
    keys = list(parsed.keys())
    assert keys[:4] == ["timestamp", "level", "component", "event"]
    assert keys[-1] == "message"
