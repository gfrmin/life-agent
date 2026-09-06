"""r51b (2a) — `scripts/atm_bench/build_kb.py`: the external KB built from ATM-Bench's files.

Layout under ``--out DIR``: ``DIR/kb`` (the second LIFE_AGENT_KB), ``DIR/emails`` as a SIBLING
(the ingest guard refuses a root inside the KB or the store), ``DIR/pkm.yaml``; the content
store at ``--store``. Every `.eml` carries only what the record can derive (Date, Subject,
Message-ID) and the detail as body — no From/To/Cc. Questions keep all-email-evidence QA
only, ``fuzzy`` from the ANSWER type, notes carrying ids never values. Counts only on stdout.
"""
from __future__ import annotations

import email
import email.policy
import hashlib
import json
import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, "scripts")

import atm_bench.build_kb as B
import run_eval
from data_source_registry import RegistryError, assert_roots_ingestable, load_registry

from pkm.producers.email_producer import EmailProducer, installed_email_version

# PII-OK: every record below is synthetic ATM-Bench-shaped data (invented ids, dates, text)
REC = {"id": "email000000000001", "timestamp": "2024-03-08T09:15:00",
       "short_summary": "Parcel collected",
       "detail": "The parcel was collected on 8 March 2024 from the depot."}
REC2 = {"id": "email000000000002", "timestamp": "2024-03-09T10:00:00",
        "short_summary": "Chairs ordered", "detail": "Twelve chairs were ordered for the hall."}
QA_EMAIL = {"id": "atm-q1", "question": "When was the parcel collected?",
            "answer": "8 March 2024", "evidence_ids": ["email000000000001"]}
QA_MIXED = {"id": "atm-q2", "question": "What was in the photo?", "answer": "a hall",
            "evidence_ids": ["email000000000001", "20240308_091500"]}
QA_OPEN = {"id": "atm-q3", "question": "Where was the parcel collected from?",
           "answer": "the depot", "evidence_ids": ["email000000000001"]}
QA_COUNT = {"id": "atm-q4", "question": "How many chairs were ordered?", "answer": "12",
            "evidence_ids": ["email000000000002"]}


def _parse(raw: bytes) -> email.message.EmailMessage:
    msg = email.message_from_bytes(raw, policy=email.policy.default)
    assert isinstance(msg, email.message.EmailMessage)
    return msg


# --- the .eml ---------------------------------------------------------------------------------


def test_eml_carries_only_the_three_derivable_headers_and_the_body() -> None:
    msg = _parse(B.eml_bytes(REC))
    assert msg["Subject"] == "Parcel collected"
    assert msg["Message-ID"] == "<email000000000001@atm-bench>"
    assert msg["Date"] is not None and "Mar 2024" in str(msg["Date"])
    for absent in ("From", "To", "Cc"):
        assert msg[absent] is None
    body = msg.get_body(preferencelist=("plain",))
    assert body is not None and body.get_content().strip() == REC["detail"]


def test_eml_omits_date_when_timestamp_unparseable() -> None:
    msg = _parse(B.eml_bytes({**REC, "timestamp": "not a time"}))
    assert msg["Date"] is None
    assert msg["Subject"] == "Parcel collected"


def test_eml_renders_through_the_deployed_email_producer(tmp_path: Path) -> None:
    # the deployed producer end-to-end (`M-7`): the rendered text carries Subject + detail
    p = tmp_path / "e.eml"
    p.write_bytes(B.eml_bytes(REC))
    res = EmailProducer(installed_email_version()).produce(p, "h", {})
    assert res.status == "success" and res.content is not None
    text = res.content.decode("utf-8")
    assert "Subject: Parcel collected" in text and REC["detail"] in text
    assert "From:" not in text and "To:" not in text


# --- the questions ----------------------------------------------------------------------------


def test_question_for_keeps_only_all_email_evidence() -> None:
    assert B.question_for(QA_MIXED) is None
    assert B.question_for({**QA_EMAIL, "evidence_ids": []}) is None
    q = B.question_for(QA_EMAIL)
    assert q is not None
    assert (q["id"], q["question"], q["answer"]) == ("atm-q1", QA_EMAIL["question"], "8 March 2024")
    assert q["fuzzy"] is False and q["subject"] == "n/a" and q["answer_variants"] == []


def test_question_for_marks_non_number_answers_fuzzy() -> None:
    assert B.question_for(QA_OPEN)["fuzzy"] is True       # type: ignore[index]
    assert B.question_for(QA_COUNT)["fuzzy"] is False     # type: ignore[index]


def test_notes_carry_ids_not_values() -> None:
    notes = B.question_for(QA_EMAIL)["notes"]             # type: ignore[index]
    assert "email000000000001" in notes
    assert "8 March" not in notes and "depot" not in notes


def test_questions_yaml_loads_through_run_eval_load_questions(tmp_path: Path) -> None:
    path = tmp_path / "questions.yaml"
    n = B.write_questions(path, [QA_EMAIL, QA_MIXED, QA_OPEN, QA_COUNT])
    assert n == 3
    qs = run_eval.load_questions(path)
    assert [q["id"] for q in qs] == ["atm-q1", "atm-q3", "atm-q4"]
    assert qs[0]["question"] == QA_EMAIL["question"]        # verbatim: the hash join needs it
    assert qs[0]["search_queries"] == [] and qs[0]["distractors"] == []


# --- registry, pkm config, owner, gauge, manifest ---------------------------------------------


def test_registry_doc_passes_the_ingest_guard_only_as_a_sibling(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    out, store = tmp_path / "r51", tmp_path / "store"
    kb, emails = out / "kb", out / "emails"
    for d in (kb, emails, store, kb / "emails"):
        d.mkdir(parents=True)
    monkeypatch.setenv("LIFE_AGENT_KB", str(kb))
    pkm_yaml = out / "pkm.yaml"
    pkm_yaml.write_text(yaml.safe_dump(B.pkm_config_doc(store)), encoding="utf-8")
    reg = tmp_path / "reg.yaml"
    reg.write_text(yaml.safe_dump(B.registry_doc(emails)), encoding="utf-8")
    roots = load_registry(reg).roots
    assert [r.id for r in roots] == ["atm-bench"] and roots[0].include == ("**/*.eml",)
    assert_roots_ingestable(roots, pkm_config=pkm_yaml)      # the sibling passes
    reg.write_text(yaml.safe_dump(B.registry_doc(kb / "emails")), encoding="utf-8")
    with pytest.raises(RegistryError):
        assert_roots_ingestable(load_registry(reg).roots, pkm_config=pkm_yaml)


def test_pkm_config_doc_binds_the_producer_version(tmp_path: Path) -> None:
    doc = B.pkm_config_doc(tmp_path / "store")
    assert doc["root_dir"] == str(tmp_path / "store")
    assert set(doc["extractors"]) == {"email"}
    assert doc["extractors"]["email"]["version"] == installed_email_version()


def test_copy_gauge_copies_exactly_two_files_and_records_their_hashes(tmp_path: Path) -> None:
    real, kb = tmp_path / "real", tmp_path / "kb"
    (real / "utility").mkdir(parents=True)
    (real / "utility" / "model.yaml").write_text("model: x\n", encoding="utf-8")
    (real / "utility" / "elicitations.jsonl").write_text('{"e": 1}\n', encoding="utf-8")
    (real / "utility" / "extra.yaml").write_text("never: copied\n", encoding="utf-8")
    shas = B.copy_gauge(real, kb)
    assert set(shas) == {"utility/model.yaml", "utility/elicitations.jsonl"}
    assert sorted(p.name for p in (kb / "utility").iterdir()) == ["elicitations.jsonl",
                                                                   "model.yaml"]
    assert shas["utility/model.yaml"] == hashlib.sha256(b"model: x\n").hexdigest()


def test_pkm_steps_are_the_bootstrap_recipe_in_order(tmp_path: Path) -> None:
    steps = B.pkm_steps(tmp_path / "repo", tmp_path / "pkm.yaml", tmp_path / "kb")
    heads = [" ".join(s[-3:]) for s in steps]
    assert [h.split()[-1] for h in heads[:1]] == ["migrate"]
    assert any("ingest_sources.py" in " ".join(s) for s in steps)
    assert any(s[-2:] == ["--producer", "email"] for s in steps)
    assert any(s[-2:] == ["chunk", "--backfill"] for s in steps)
    assert steps[-1][-1] == "rebuild-index"
    assert all(s[:3] == ["uv", "run", "--project"] for s in steps)


def test_run_pkm_steps_sets_the_kb_and_config_and_drops_the_membrane(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import subprocess

    seen: list[tuple[list[str], dict[str, str]]] = []

    def fake_run(cmd: list[str], **kw: object) -> subprocess.CompletedProcess[str]:
        seen.append((list(cmd), dict(kw["env"])))          # type: ignore[arg-type]
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setenv("LIFE_AGENT_MEMBRANE_COMMAND", str(tmp_path / "engine"))
    monkeypatch.setattr(subprocess, "run", fake_run)
    B.run_pkm_steps(tmp_path / "repo", tmp_path / "pkm.yaml", tmp_path / "kb")
    assert len(seen) == 5
    for _cmd, env in seen:
        assert env["LIFE_AGENT_KB"] == str(tmp_path / "kb")
        assert env["PKM_CONFIG"] == str(tmp_path / "pkm.yaml")
        assert "LIFE_AGENT_MEMBRANE_COMMAND" not in env


# --- main: the layout, counts only, idempotent ------------------------------------------------


def _inputs(tmp_path: Path) -> tuple[Path, Path, Path]:
    emails = tmp_path / "emails.json"
    emails.write_text(json.dumps([REC, REC2]), encoding="utf-8")
    qa = tmp_path / "atm-bench.json"
    qa.write_text(json.dumps([QA_EMAIL, QA_MIXED, QA_OPEN, QA_COUNT]), encoding="utf-8")
    real = tmp_path / "real-kb"
    (real / "utility").mkdir(parents=True)
    (real / "utility" / "model.yaml").write_text("model: x\n", encoding="utf-8")
    (real / "utility" / "elicitations.jsonl").write_text('{"e": 1}\n', encoding="utf-8")
    return emails, qa, real


def _snapshot(root: Path) -> dict[str, tuple[int, bytes]]:
    return {str(p.relative_to(root)): (p.stat().st_mtime_ns, p.read_bytes())
            for p in root.rglob("*") if p.is_file()}


def test_main_builds_the_layout_prints_counts_only_and_a_second_run_writes_nothing(
        tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    emails, qa, real = _inputs(tmp_path)
    out, store = tmp_path / "r51", tmp_path / "store"
    argv = ["--emails", str(emails), "--qa", str(qa), "--out", str(out), "--store", str(store),
            "--gauge-from", str(real), "--hf-revision", "abc123", "--no-pkm"]
    assert B.main(argv) == 0
    kb = out / "kb"
    for rel in ("kb/config/data-sources.yaml", "kb/owner.md", "kb/eval/questions.yaml",
                "kb/pii-patterns.txt", "kb/utility/model.yaml",
                "kb/utility/elicitations.jsonl", "pkm.yaml", "emails/email000000000001.eml",
                "emails/email000000000002.eml", f"kb/{B.MANIFEST}"):
        assert (out / rel).is_file(), rel
    manifest = json.loads((kb / B.MANIFEST).read_text(encoding="utf-8"))
    assert manifest["corpus"] == "atm-bench" and manifest["hf_revision"] == "abc123"
    assert manifest["counts"]["emails"] == 2 and manifest["counts"]["questions"] == 3
    assert manifest["counts"]["gradeable"] == 2
    assert set(manifest["gauge"]) == {"utility/model.yaml", "utility/elicitations.jsonl"}
    assert manifest["evaluator_sha"].startswith("ef4e5dff")
    text = capsys.readouterr().out
    assert "emails=2" in text and "questions=3" in text
    for value in (REC["detail"], "8 March", "depot", "Parcel collected"):
        assert value not in text                             # counts only, never a value
    before = _snapshot(out)
    assert B.main(argv) == 0
    assert _snapshot(out) == before                           # a second run writes nothing


def test_main_refuses_a_gauge_source_without_both_files(tmp_path: Path) -> None:
    emails, qa, real = _inputs(tmp_path)
    (real / "utility" / "elicitations.jsonl").unlink()
    rc = B.main(["--emails", str(emails), "--qa", str(qa), "--out", str(tmp_path / "o"),
                 "--store", str(tmp_path / "s"), "--gauge-from", str(real), "--no-pkm"])
    assert rc == 2


def test_eml_subject_collapses_line_breaks_and_runs_of_whitespace() -> None:
    # the released summaries can carry a line break; a header value may not (the stdlib
    # refuses it), and the producer renders one header per line anyway
    rec = {**REC, "short_summary": "Parcel\r\n collected\n\tat the depot"}
    msg = _parse(B.eml_bytes(rec))
    assert msg["Subject"] == "Parcel collected at the depot"
