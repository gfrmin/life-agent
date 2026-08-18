"""The unified-ledger schema and segment store — design §2 / §10, owner S6.

Every fixture is synthetic by construction (# PII-OK: synthetic records throughout)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from life_agent.ledger import schema as S
from life_agent.ledger import store as ST


def _ev(seq: int, n: int = 0, source: str = "calibration.reactions") -> S.UnifiedEvent:
    return S.UnifiedEvent(source_id=source, seq=seq, tx_time_raw="2026-01-01T00:00:00+00:00",
                          kernel_id="owner:verdict", author="owner",
                          record={"decision_id": "ab-" + f"{n:032x}", "valence": "good"})


# --- schema ----------------------------------------------------------------------------------

def test_event_id_is_sha_over_source_seq_record_and_ignores_derived_fields() -> None:
    a = _ev(1)
    b = S.UnifiedEvent(**{**a.__dict__, "event_id": "", "tx_time": "2026-01-01T00:00:00Z"})
    assert a.event_id == b.event_id == S.event_id(a.source_id, 1, a.record)
    assert _ev(1).event_id != _ev(2).event_id            # same record, different ordinal
    assert _ev(1, source="act.tasks").event_id != _ev(1).event_id


def test_vocabularies_are_loud() -> None:
    with pytest.raises(ValueError):
        S.UnifiedEvent(source_id="nope", seq=1, tx_time_raw="t", kernel_id="owner:x",
                       author="owner", record={})
    with pytest.raises(ValueError):
        S.UnifiedEvent(source_id="act.tasks", seq=1, tx_time_raw="t", kernel_id="owner:x",
                       author="robot", record={})
    with pytest.raises(ValueError):
        S.UnifiedEvent(source_id="act.tasks", seq=1, tx_time_raw="t", kernel_id="mystery:x",
                       author="owner", record={})
    with pytest.raises(ValueError):
        S.UnifiedEvent(source_id="act.tasks", seq=0, tx_time_raw="t", kernel_id="owner:x",
                       author="owner", record={})
    with pytest.raises(ValueError):
        S.UnifiedEvent(source_id="act.tasks", seq=1, tx_time_raw="t", kernel_id="owner:x",
                       author="owner", record={}, event_id="00" * 32)


def test_line_roundtrip_is_canonical() -> None:
    e = _ev(3)
    line = S.to_line(e)
    assert line == S.to_line(S.from_line(line))
    assert json.loads(line) == json.loads(S.canonical(json.loads(line)))


# --- store: append / read / density / idempotence ----------------------------------------------

def test_append_read_roundtrip_dense_seq_and_idempotent_reappend(tmp_path: Path) -> None:
    st = ST.LedgerStore(tmp_path / "ledger")
    assert st.append(_ev(1, 1)) is True
    assert st.append(_ev(2, 2)) is True
    assert st.append(_ev(2, 2)) is False                 # identical event at an occupied ordinal
    with pytest.raises(ST.LedgerConflictError):
        st.append(_ev(2, 99))                             # different event at an occupied ordinal
    with pytest.raises(ST.LedgerConflictError):
        st.append(_ev(4, 4))                              # a gap
    got = st.read("calibration.reactions")
    assert [e.seq for e in got] == [1, 2]
    assert st.next_seq("calibration.reactions") == 3
    assert (tmp_path / "ledger" / "calibration.reactions.jsonl").read_bytes().endswith(b"\n")


def test_reader_is_loud_on_unlisted_garbage(tmp_path: Path) -> None:
    st = ST.LedgerStore(tmp_path / "ledger")
    st.append(_ev(1, 1))
    seg = st.segment_path("calibration.reactions")
    with seg.open("ab") as fh:
        fh.write(b"{not json}\n")
    with pytest.raises(ST.LedgerReadError) as ei:
        st.read("calibration.reactions")
    assert "physical line 2" in str(ei.value)


# --- the torn-tail protocol (design §10; owner S6) --------------------------------------------

def _tear(seg: Path, event: S.UnifiedEvent, keep: int = 20) -> bytes:
    """Simulate a crash mid-write: append the first `keep` bytes of a line, no newline."""
    torn = S.to_line(event).encode("utf-8")[:keep]
    with seg.open("ab") as fh:
        fh.write(torn)
    return torn


def test_torn_tail_is_quarantined_ordinal_reused_bytes_untouched(tmp_path: Path) -> None:
    st = ST.LedgerStore(tmp_path / "ledger")
    st.append(_ev(1, 1))
    seg = st.segment_path("calibration.reactions")
    before = seg.read_bytes()
    torn = _tear(seg, _ev(2, 2))
    # A torn line was never an event: the reader (no writer has opened yet) is loud on it,
    # and the parseable count is still 1.
    with pytest.raises(ST.LedgerReadError):
        st.read("calibration.reactions")
    # The writer opens: quarantines the tail (manifest), terminates it, appends seq 2 — the
    # torn ordinal is REUSED and the event_id is what the torn line's would have been.
    assert st.append(_ev(2, 2)) is True
    q = st.quarantine("calibration.reactions")
    assert len(q) == 1
    assert q[0].byte_offset == len(before) and q[0].length == len(torn)
    assert bytes.fromhex(q[0].bytes_hex) == torn and q[0].reason == "unterminated"
    data = seg.read_bytes()
    assert data.startswith(before + torn + b"\n")        # segment never truncated (S6)
    got = st.read("calibration.reactions")
    assert [e.seq for e in got] == [1, 2] and got[1].event_id == _ev(2, 2).event_id
    # Reader: silent inside the quarantined range, dense seq verified.
    assert st.parseable_count("calibration.reactions") == 2
    # Idempotent re-append of the same canonical line is a no-op.
    assert st.append(_ev(2, 2)) is False


def test_quarantine_entries_are_permanent_and_manifest_is_additive(tmp_path: Path) -> None:
    st = ST.LedgerStore(tmp_path / "ledger")
    st.append(_ev(1, 1))
    seg = st.segment_path("calibration.reactions")
    _tear(seg, _ev(2, 2))
    st.append(_ev(2, 2))
    st.append(_ev(3, 3))
    _tear(seg, _ev(4, 4), keep=7)
    st.append(_ev(4, 4))
    q = st.quarantine("calibration.reactions")
    assert len(q) == 2                                   # nothing removed, nothing compacted (S6)
    assert [e.seq for e in st.read("calibration.reactions")] == [1, 2, 3, 4]
    m = json.loads(st.manifest_path.read_text(encoding="utf-8"))
    assert len(m["quarantine"]) == 2 and m["format_version"] == ST.MANIFEST_FORMAT_VERSION
    st.record_source_counts("calibration.reactions", unparseable=0, duplicate_key_lines=0)
    st.set_epoch("2026-01-01T00:00:00+00:00")
    m2 = json.loads(st.manifest_path.read_text(encoding="utf-8"))
    assert m2["quarantine"] == m["quarantine"]           # additive writes preserve quarantine
    assert m2["sources"]["calibration.reactions"]["unparseable"] == 0
    assert m2["epoch"] == "2026-01-01T00:00:00+00:00"


def test_terminated_but_unparseable_tail_is_quarantined_too(tmp_path: Path) -> None:
    st = ST.LedgerStore(tmp_path / "ledger")
    st.append(_ev(1, 1))
    seg = st.segment_path("calibration.reactions")
    with seg.open("ab") as fh:
        fh.write(b'{"half": \n')
    st.append(_ev(2, 2))
    q = st.quarantine("calibration.reactions")
    assert len(q) == 1 and q[0].reason == "unparseable"
    assert [e.seq for e in st.read("calibration.reactions")] == [1, 2]


def test_segments_are_per_source_and_a_foreign_event_in_a_segment_is_loud(tmp_path: Path) -> None:
    st = ST.LedgerStore(tmp_path / "ledger")
    st.append(_ev(1, 1))
    st.append(_ev(1, 1, source="act.tasks"))
    assert st.segment_path("act.tasks") != st.segment_path("calibration.reactions")
    assert [e.source_id for e in st.read("act.tasks")] == ["act.tasks"]
    # a line whose source_id disagrees with its segment is a read error, not a silent merge
    seg = st.segment_path("act.tasks")
    with seg.open("ab") as fh:
        fh.write(S.to_line(_ev(2, 2)).encode("utf-8") + b"\n")
    with pytest.raises(ST.LedgerReadError):
        st.read("act.tasks")
