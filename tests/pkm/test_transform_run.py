"""Integration tests for ``pkm.transform_run`` -- the transform orchestration.

The centrepiece is the 50-source run exercising the full pipeline:
declaration loading, policy evaluation, producer dispatch, artifact
writing with lineage, telemetry logging, and cache-hit idempotency.

All tests use a mock LLM client that returns deterministic entity
extraction results with correct spans.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from pkm.cache import write_artifact
from pkm.catalogue import open_catalogue
from pkm.config import Config
from pkm.hashing import compute_cache_key
from pkm.producer import ProducerResult
from pkm.transform_run import run_transform
from pkm.transforms.entity_extraction import EntityExtractionProducer

# --- Fixtures and helpers ------------------------------------------------

_EXAMPLES_DIR = (
    Path(__file__).resolve().parent.parent
    / "examples" / "transforms" / "entity_extraction" / "v1"
)

_DOCUMENTS: list[tuple[str, list[str]]] = [
    ("Alice Johnson works at Acme Corp in London.", ["legal"]),
    ("Bob Smith visited Paris on 2025-03-15.", ["travel"]),
    ("Carol White earned $50,000 at TechStart.", ["financial"]),
    ("David Brown met Eve Davis in New York.", []),
    ("Frank Miller joined GlobalBank on 2024-01-01.", ["financial"]),
    ("Grace Lee lives in Tokyo and works at Sony.", []),
    ("Henry Wilson founded StartupXYZ in Berlin.", []),
    ("Iris Chen published research at MIT.", ["academic"]),
    ("Jack Taylor sold $1,200,000 of property in Chicago.", ["financial"]),
    ("Karen Adams moved from Sydney to Melbourne.", ["travel"]),
    ("Leo Martin works at Amazon in Seattle.", []),
    ("Maria Garcia visited Rome on 2025-06-20.", ["travel"]),
    ("Nathan Patel earned $75,000 at DataCorp.", ["financial"]),
    ("Olivia Kim joined Netflix in Los Angeles.", []),
    ("Peter Scott founded BioTech in Boston.", ["academic"]),
    ("Quinn Harris lives in Dublin and works at Google.", []),
    ("Rachel Turner visited Barcelona on 2024-12-01.", ["travel"]),
    ("Sam Cooper earned $90,000 at FinanceHub.", ["financial"]),
    ("Tina Nguyen works at Apple in Cupertino.", []),
    ("Uma Sharma visited London on 2025-01-10.", ["travel"]),
    ("Victor Reyes joined Microsoft in Redmond.", []),
    ("Wendy Liu published work at Stanford.", ["academic"]),
    ("Xavier Morris sold $2,500,000 of stock in Houston.", ["financial"]),
    ("Yuki Tanaka moved from Osaka to Kyoto.", ["travel"]),
    ("Zara Phillips works at Meta in Menlo Park.", []),
    ("Aaron Brooks founded EdTech in Austin.", []),
    ("Beth Collins earned $110,000 at HealthOrg.", ["financial"]),
    ("Chris Evans visited Munich on 2025-04-05.", ["travel"]),
    ("Diana Ross lives in Nashville and works at Spotify.", []),
    ("Edward Young joined Tesla in Palo Alto.", []),
    ("Fiona Clark published research at Oxford.", ["academic"]),
    ("George Hall sold $800,000 of bonds in Denver.", ["financial"]),
    ("Hannah Price moved from Portland to San Diego.", ["travel"]),
    ("Ivan Petrov works at Yandex in Moscow.", []),
    ("Julia Stone founded AgriTech in Sacramento.", []),
    ("Kevin Moore earned $65,000 at RetailCo.", ["financial"]),
    ("Laura King visited Vienna on 2024-09-15.", ["travel"]),
    ("Michael Chan works at Samsung in Seoul.", []),
    ("Nicole Ford joined Oracle in San Jose.", []),
    ("Oscar Green published work at Cambridge.", ["academic"]),
    ("Paula White lives in Prague and works at Red Hat.", []),
    ("Ryan Hughes founded CloudCo in Denver.", []),
    ("Sarah West earned $120,000 at ConsultGroup.", ["financial"]),
    ("Thomas Black visited Lisbon on 2025-02-28.", ["travel"]),
    ("Ursula Park works at Intel in Portland.", []),
    ("Vincent Diaz joined Adobe in San Francisco.", []),
    ("Whitney Hill published research at Harvard.", ["academic"]),
    ("Xander Blake sold $500,000 of assets in Miami.", ["financial"]),
    ("Patient Jane Doe was diagnosed at City Hospital.", ["sensitive", "medical"]),
    ("Zoe Grant works at IBM in Armonk.", []),
]


def _find_entities(text: str) -> list[dict[str, Any]]:
    """Deterministic entity extraction for testing.

    Finds capitalised multi-word names (person), known org patterns,
    locations, dates, and money amounts with correct spans.
    """
    entities: list[dict[str, Any]] = []

    for m in re.finditer(
        r"\$[\d,]+(?:\.\d+)?", text,
    ):
        entities.append({
            "text": m.group(),
            "type": "money",
            "span": {"start": m.start(), "end": m.end()},
            "confidence": 0.9,
        })

    for m in re.finditer(
        r"\b\d{4}-\d{2}-\d{2}\b", text,
    ):
        entities.append({
            "text": m.group(),
            "type": "date",
            "span": {"start": m.start(), "end": m.end()},
            "confidence": 0.95,
        })

    for m in re.finditer(
        r"\b[A-Z][a-z]+ [A-Z][a-z]+\b", text,
    ):
        name = m.group()
        if name in (
            "City Hospital", "Red Hat",
        ):
            entities.append({
                "text": name,
                "type": "organization",
                "span": {"start": m.start(), "end": m.end()},
                "confidence": 0.85,
            })
        elif any(
            name.startswith(p)
            for p in ("Patient", "Dr")
        ):
            continue
        else:
            entities.append({
                "text": name,
                "type": "person",
                "span": {"start": m.start(), "end": m.end()},
                "confidence": 0.9,
            })

    return entities


@dataclass
class _MockUsage:
    input_tokens: int = 100
    output_tokens: int = 50


@dataclass
class _MockTextBlock:
    text: str = ""
    type: str = "text"


@dataclass
class _MockResponse:
    content: list[_MockTextBlock]
    usage: _MockUsage


def _make_mock_client() -> MagicMock:
    """Mock Anthropic client that returns deterministic entity extractions."""
    client = MagicMock()

    def create_response(**kwargs: Any) -> _MockResponse:
        prompt = kwargs.get("messages", [{}])[0].get("content", "")
        marker = "---\n"
        idx = prompt.find(marker)
        if idx >= 0:
            text = prompt[idx + len(marker):]
            end_idx = text.rfind("\n---")
            if end_idx >= 0:
                text = text[:end_idx]
        else:
            text = prompt

        entities = _find_entities(text)
        output = {"format_version": 1, "entities": entities}

        return _MockResponse(
            content=[_MockTextBlock(text=json.dumps(output))],
            usage=_MockUsage(input_tokens=100, output_tokens=50),
        )

    client.messages.create.side_effect = create_response
    return client


def _setup_transform_root(
    root: Path,
    *,
    budget: float = 50.0,
    sensitive_tags: list[str] | None = None,
) -> Config:
    """Set up a complete transform-ready root with 50 sources."""
    (root / "transforms").mkdir(exist_ok=True)
    (root / "prompts").mkdir(exist_ok=True)
    (root / "schemas").mkdir(exist_ok=True)
    (root / "policies").mkdir(exist_ok=True)

    import shutil
    for subdir in ("transforms", "prompts", "schemas", "policies"):
        src = _EXAMPLES_DIR / subdir
        dst = root / subdir
        for f in src.iterdir():
            if f.is_file():
                shutil.copy2(f, dst / f.name)

    stags = sensitive_tags or ["sensitive", "medical"]
    cfg_path = root / "config.yaml"
    cfg_path.write_text(
        f"root_dir: {root}\n"
        "policies:\n"
        "  cost_gate:\n"
        f"    budget_per_invocation_usd: {budget}\n"
        "    budget_per_day_usd: 500.00\n"
        "    budget_per_month_usd: 2000.00\n"
        "  sensitive_doc_gate:\n"
        f"    tags: {json.dumps(stags)}\n"
        "    path_patterns: []\n",
        encoding="utf-8",
    )

    with open_catalogue(root) as conn:
        for i, (text, tags) in enumerate(_DOCUMENTS):
            source_content = text.encode("utf-8")
            source_id = hashlib.sha256(source_content).hexdigest()
            source_path = root / "sources" / f"doc_{i:03d}.txt"
            source_path.write_text(text, encoding="utf-8")

            conn.execute(
                "INSERT OR IGNORE INTO sources "
                "(source_id, current_path, first_seen, last_seen, "
                " size_bytes) "
                "VALUES (?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, ?)",
                [source_id, str(source_path), len(source_content)],
            )
            conn.execute(
                "INSERT OR IGNORE INTO source_paths "
                "(source_id, path, seen_at) "
                "VALUES (?, ?, CURRENT_TIMESTAMP)",
                [source_id, str(source_path)],
            )
            for tag in tags:
                conn.execute(
                    "INSERT OR IGNORE INTO source_tags "
                    "(source_id, tag) VALUES (?, ?)",
                    [source_id, tag],
                )

            extractor_ck = compute_cache_key(
                input_hash=source_id,
                producer_name="pandoc",
                producer_version="3.1.9",
                producer_config={},
            )
            write_artifact(
                root, conn,
                cache_key=extractor_ck,
                input_hash=source_id,
                producer_name="pandoc",
                producer_version="3.1.9",
                producer_config={},
                result=ProducerResult(
                    status="success",
                    content=source_content,
                    content_type="text/plain",
                    content_encoding="utf-8",
                    error_message=None,
                    producer_metadata={"completion": "complete"},
                ),
            )

    from pkm.config import load_config

    return load_config(cfg_path)


@pytest.fixture
def transform_root(migrated_root: Path) -> tuple[Path, Config]:
    config = _setup_transform_root(migrated_root)
    return migrated_root, config


@pytest.fixture
def transform_root_no_sensitive(
    migrated_root: Path,
) -> tuple[Path, Config]:
    config = _setup_transform_root(
        migrated_root, sensitive_tags=["nonexistent_tag"],
    )
    return migrated_root, config


# --- 50-source run tests -------------------------------------------------


def test_50_source_run_completes(
    transform_root_no_sensitive: tuple[Path, Config],
) -> None:
    """Stage B exit criterion: 50-source run completes, >= 48/50 succeed."""
    root, config = transform_root_no_sensitive
    client = _make_mock_client()

    from pkm.transform_declaration import load_transform_declaration

    decl = load_transform_declaration(root, "entity_extraction")
    producer = EntityExtractionProducer(declaration=decl, client=client)

    result = run_transform(
        root, config, "entity_extraction",
        producer_override=producer,
    )

    assert result.total_sources == 50
    assert result.processed == 50
    assert result.succeeded >= 48
    assert not result.approval_required
    assert not result.blocked


def test_cache_hit_on_second_run(
    transform_root_no_sensitive: tuple[Path, Config],
) -> None:
    root, config = transform_root_no_sensitive
    client = _make_mock_client()

    from pkm.transform_declaration import load_transform_declaration

    decl = load_transform_declaration(root, "entity_extraction")
    producer = EntityExtractionProducer(declaration=decl, client=client)

    run_transform(root, config, "entity_extraction", producer_override=producer)
    result2 = run_transform(
        root, config, "entity_extraction", producer_override=producer,
    )

    assert result2.cache_hits == 50
    assert result2.succeeded == 0
    assert result2.failed == 0


def test_telemetry_logged(
    transform_root_no_sensitive: tuple[Path, Config],
) -> None:
    root, config = transform_root_no_sensitive
    client = _make_mock_client()

    from pkm.transform_declaration import load_transform_declaration

    decl = load_transform_declaration(root, "entity_extraction")
    producer = EntityExtractionProducer(declaration=decl, client=client)

    run_transform(root, config, "entity_extraction", producer_override=producer)

    log_dir = root / "logs" / "transforms"
    log_files = list(log_dir.glob("*.jsonl"))
    assert len(log_files) >= 1
    lines = log_files[0].read_text(encoding="utf-8").strip().split("\n")
    assert len(lines) == 50


def test_lineage_recorded(
    transform_root_no_sensitive: tuple[Path, Config],
) -> None:
    root, config = transform_root_no_sensitive
    client = _make_mock_client()

    from pkm.transform_declaration import load_transform_declaration

    decl = load_transform_declaration(root, "entity_extraction")
    producer = EntityExtractionProducer(declaration=decl, client=client)

    run_transform(root, config, "entity_extraction", producer_override=producer)

    with open_catalogue(root) as conn:
        rows = conn.execute(
            "SELECT COUNT(*) FROM artifact_lineage "
            "WHERE role = 'source_text'",
        ).fetchone()
    assert rows is not None
    assert rows[0] == 50


def test_progress_callback_called(
    transform_root_no_sensitive: tuple[Path, Config],
) -> None:
    root, config = transform_root_no_sensitive
    client = _make_mock_client()

    from pkm.transform_declaration import load_transform_declaration

    decl = load_transform_declaration(root, "entity_extraction")
    producer = EntityExtractionProducer(declaration=decl, client=client)

    lines: list[str] = []
    run_transform(
        root, config, "entity_extraction",
        producer_override=producer,
        progress=lines.append,
    )
    assert len(lines) == 50


# --- Policy trigger tests ------------------------------------------------


def test_sensitive_doc_gate_requires_approval(
    transform_root: tuple[Path, Config],
) -> None:
    """sensitive_doc_gate triggers on the 'sensitive' tagged document."""
    root, config = transform_root
    client = _make_mock_client()

    from pkm.transform_declaration import load_transform_declaration

    decl = load_transform_declaration(root, "entity_extraction")
    producer = EntityExtractionProducer(declaration=decl, client=client)

    result = run_transform(
        root, config, "entity_extraction",
        producer_override=producer,
    )

    assert result.approval_required
    assert result.approval_id is not None
    assert result.processed == 0


def test_cost_gate_blocks_over_budget(
    migrated_root: Path,
) -> None:
    """cost_gate blocks when budget is set very low."""
    config = _setup_transform_root(
        migrated_root,
        budget=0.001,
        sensitive_tags=["nonexistent_tag"],
    )
    client = _make_mock_client()

    from pkm.transform_declaration import load_transform_declaration

    decl = load_transform_declaration(migrated_root, "entity_extraction")
    producer = EntityExtractionProducer(declaration=decl, client=client)

    result = run_transform(
        migrated_root, config, "entity_extraction",
        producer_override=producer,
    )

    assert result.blocked
    assert result.block_reason is not None
    reason = result.block_reason.lower()
    assert "cost" in reason or "budget" in reason


# --- Approval flow -------------------------------------------------------


def test_approval_then_run(
    transform_root: tuple[Path, Config],
) -> None:
    """After approval, the run proceeds with --approval-id."""
    root, config = transform_root
    client = _make_mock_client()

    from pkm.transform_declaration import load_transform_declaration

    decl = load_transform_declaration(root, "entity_extraction")
    producer = EntityExtractionProducer(declaration=decl, client=client)

    result1 = run_transform(
        root, config, "entity_extraction",
        producer_override=producer,
    )
    assert result1.approval_required
    aid = result1.approval_id

    from pkm.approval import approve

    with open_catalogue(root) as conn:
        approve(conn, aid)

    result2 = run_transform(
        root, config, "entity_extraction",
        approval_id=aid,
        producer_override=producer,
    )
    assert not result2.approval_required
    assert not result2.blocked
    assert result2.succeeded >= 48


# --- Limit flag ----------------------------------------------------------


def test_limit_restricts_source_count(
    transform_root_no_sensitive: tuple[Path, Config],
) -> None:
    root, config = transform_root_no_sensitive
    client = _make_mock_client()

    from pkm.transform_declaration import load_transform_declaration

    decl = load_transform_declaration(root, "entity_extraction")
    producer = EntityExtractionProducer(declaration=decl, client=client)

    result = run_transform(
        root, config, "entity_extraction",
        limit=5,
        producer_override=producer,
    )
    assert result.total_sources == 5
    assert result.processed == 5
