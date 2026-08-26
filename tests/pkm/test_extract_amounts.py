"""Tests for the ``extract_amounts`` LLM transform (SPEC §18.14, r21 phase 1).

Hermetic: a fake ``ModelClient`` returns canned line-items — no model call. Covers the
§18.5 grounding gate (an ungroundable ``amount_raw`` fails the whole source; ``label_raw``
grounds when non-null), the closed ``kind``/``basis`` enums, the empty-items determinate
success, the ``unreadable`` indeterminate, the ``majority_unlabelled`` derivation, the
currency fallback, determinism, and example-declaration loading.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from pkm.transform import ModelResponse
from pkm.transform_declaration import TransformDeclaration, load_transform_declaration
from pkm.transforms.extract_amounts import ExtractAmountsProducer

_EXAMPLES_DIR = (
    Path(__file__).resolve().parents[2]
    / "docs" / "pkm" / "examples" / "transforms" / "extract_amounts" / "v1"
)

_SCHEMA: dict[str, Any] = json.loads(
    (_EXAMPLES_DIR / "schemas" / "extract_amounts_v1.json").read_text(encoding="utf-8")
)

# PII-OK: synthetic pay statement — invented employer/amounts, Latin script.
_DOC = (
    "ACME Rockets Ltd — monthly pay statement, period 2025-07\n"
    "Gross pay            12,345.67\n"
    "Income tax            2,000.10\n"
    "Net pay              10,345.57\n"
)


def _item(**over: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "kind": "income_gross", "basis": "monthly", "as_of": "2025-07-31",
        "amount": 12345.67, "currency": "USD",
        "amount_raw": "12,345.67", "label_raw": "Gross pay", "entity": None,
    }
    base.update(over)
    return base


def _output(items: list[dict[str, Any]], **over: Any) -> dict[str, Any]:
    out: dict[str, Any] = {"currency_default": "USD", "unreadable": False,
                           "items": items}
    out.update(over)
    return out


class _FakeClient:
    engine_version = "fake-1"

    def __init__(self, output: dict[str, Any]) -> None:
        self._output = output
        self.prompts: list[str] = []

    def complete(self, prompt: str, schema: dict[str, Any]) -> ModelResponse:
        self.prompts.append(prompt)
        return ModelResponse(
            raw_text=json.dumps(self._output),
            input_tokens=10, output_tokens=5, latency_ms=1, cost_usd=0.0,
        )


def _decl(*, input_producer: str = "docling") -> TransformDeclaration:
    prompt_text = "Extract labelled amounts.\n---\n{text}\n---\n"
    return TransformDeclaration(
        name=f"extract_amounts_{input_producer}", version="0.1.0",
        producer_class="pkm.transforms.extract_amounts.ExtractAmountsProducer",
        model_identity={
            "provider": "anthropic", "model": "claude-haiku-4-5-20251001",
            "inference_params": {"temperature": 0.0},
        },
        prompt_name="extract_amounts_v1", prompt_text=prompt_text,
        prompt_hash=hashlib.sha256(prompt_text.encode()).hexdigest(),
        output_schema_name="extract_amounts_v1", output_schema=_SCHEMA,
        policies=[], input_producer=input_producer,
        input_required_status="success",
        declaration_hash="0" * 64,
    )


def _produce(tmp_path: Path, text: str, output: dict[str, Any]) -> Any:
    f = tmp_path / "doc.txt"
    f.write_text(text, encoding="utf-8")
    producer = ExtractAmountsProducer(declaration=_decl(),
                                      model_client=_FakeClient(output))
    return producer.produce(f, "ab" * 32, {})


# --- grounding (§18.5) ---------------------------------------------------------------

def test_grounded_items_succeed(tmp_path: Path) -> None:
    result = _produce(tmp_path, _DOC, _output([_item()]))
    assert result.status == "success", result.error_message
    parsed = json.loads(result.content)
    assert parsed["format_version"] == 1
    assert parsed["items"][0]["amount"] == 12345.67
    assert parsed["majority_unlabelled"] is False


def test_ungroundable_amount_fails_the_source(tmp_path: Path) -> None:
    result = _produce(tmp_path, _DOC, _output([_item(amount_raw="99,999.99")]))
    assert result.status != "success"
    assert "amount_raw" in (result.error_message or "")


def test_ungroundable_label_fails_the_source(tmp_path: Path) -> None:
    result = _produce(tmp_path, _DOC, _output([_item(label_raw="Bonus pay")]))
    assert result.status != "success"
    assert "label_raw" in (result.error_message or "")


def test_grounding_is_whitespace_normalised(tmp_path: Path) -> None:
    wrapped = _DOC.replace("Gross pay            12,345.67",
                           "Gross pay\n           12,345.67")
    result = _produce(tmp_path, wrapped,
                      _output([_item(label_raw="Gross pay 12,345.67",
                                     amount_raw="12,345.67")]))
    assert result.status == "success", result.error_message


# --- closed enums + shape ------------------------------------------------------------

def test_unknown_kind_fails(tmp_path: Path) -> None:
    result = _produce(tmp_path, _DOC, _output([_item(kind="salary")]))
    assert result.status != "success"
    assert "salary" in (result.error_message or "")


def test_unknown_basis_fails(tmp_path: Path) -> None:
    result = _produce(tmp_path, _DOC, _output([_item(basis="weekly")]))
    assert result.status != "success"
    assert "weekly" in (result.error_message or "")


def test_empty_items_is_a_determinate_success(tmp_path: Path) -> None:
    result = _produce(tmp_path, "Nothing financial here.", _output([]))
    assert result.status == "success", result.error_message
    parsed = json.loads(result.content)
    assert parsed["items"] == [] and parsed["majority_unlabelled"] is False


def test_unreadable_requires_empty_items(tmp_path: Path) -> None:
    ok = _produce(tmp_path, "ʠʣʥ soup", _output([], unreadable=True))
    assert ok.status == "success", ok.error_message
    bad = _produce(tmp_path, _DOC, _output([_item()], unreadable=True))
    assert bad.status != "success"
    assert "unreadable" in (bad.error_message or "")


# --- majority_unlabelled derivation --------------------------------------------------

def test_majority_unlabelled_derived_not_trusted(tmp_path: Path) -> None:
    two_of_three = [
        _item(),
        _item(kind="tax", amount=2000.10, amount_raw="2,000.10", label_raw=None),
        _item(kind="income_net", amount=10345.57, amount_raw="10,345.57",
              label_raw=None),
    ]
    result = _produce(tmp_path, _DOC,
                      _output(two_of_three, majority_unlabelled=False))
    assert result.status == "success", result.error_message
    assert json.loads(result.content)["majority_unlabelled"] is True  # overridden

    half = [_item(),
            _item(kind="tax", amount=2000.10, amount_raw="2,000.10",
                  label_raw=None)]
    result = _produce(tmp_path, _DOC, _output(half))
    assert result.status == "success", result.error_message
    assert json.loads(result.content)["majority_unlabelled"] is False  # half ≠ majority


# --- currency ------------------------------------------------------------------------

def test_missing_currency_falls_back_to_default(tmp_path: Path) -> None:
    result = _produce(tmp_path, _DOC, _output([_item(currency=None)]))
    assert result.status == "success", result.error_message
    assert json.loads(result.content)["items"][0]["currency"] == "USD"


def test_no_currency_anywhere_fails(tmp_path: Path) -> None:
    result = _produce(tmp_path, _DOC,
                      _output([_item(currency=None)], currency_default=None))
    assert result.status != "success"
    assert "currency" in (result.error_message or "")


# --- determinism ---------------------------------------------------------------------

def test_same_input_same_bytes(tmp_path: Path) -> None:
    a = _produce(tmp_path, _DOC, _output([_item()]))
    b = _produce(tmp_path, _DOC, _output([_item()]))
    assert a.status == b.status == "success"
    assert a.content == b.content


# --- example declarations ------------------------------------------------------------

def test_example_declarations_load() -> None:
    for producer in ("docling", "pandoc", "tesseract", "email"):
        decl = load_transform_declaration(
            _EXAMPLES_DIR, f"extract_amounts_{producer}")
        assert decl.producer_class.endswith("ExtractAmountsProducer")
        assert decl.input_producer == producer
        assert decl.output_schema["properties"]["items"]["maxItems"] == 8
