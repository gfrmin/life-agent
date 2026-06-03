"""TransformProducer — LLM-backed producer base class (SPEC v0.2.0 §20).

A transform takes extractor output (text, structured docs) and sends
it through an LLM to produce structured JSON.  The pipeline is:

    render_prompt → call_model → parse_output → validate → write

``TransformProducer`` is an abstract base class rather than a Protocol
because the ``produce`` orchestration is shared across all transforms.
Concrete subclasses supply only the three abstract methods; the
orchestration (including schema validation, lineage assembly, and
error normalisation) lives in the base class.

Stage A (substrate): a stub subclass in the test suite exercises the
full path with hard-coded JSON.  No real LLM calls exist at this
stage.
"""

from __future__ import annotations

import hashlib
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import jsonschema

from pkm.hashing import canonical_json
from pkm.producer import ProducerResult

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ModelResponse:
    """Return value of ``call_model``.

    Captures everything the telemetry log (§23.1) needs about a
    single LLM invocation.
    """

    raw_text: str
    input_tokens: int
    output_tokens: int
    latency_ms: int
    cost_usd: float


class TransformProducer(ABC):
    """Base class for LLM-backed producers (SPEC v0.2.0 §20.1).

    Subclasses MUST set ``name``, ``version``, ``model_identity``,
    and ``prompt_name`` as instance or class attributes, and implement
    the three abstract methods.

    The ``produce`` method orchestrates the pipeline and never raises
    (failures become ``ProducerResult(status="failed", ...)``).
    """

    name: str
    version: str
    model_identity: dict[str, Any]
    prompt_name: str
    output_schema: dict[str, Any]
    # Inference-engine / SDK version string, part of the event identity
    # (SPEC v0.3.0 §29 / PRINCIPLES §2). Concrete producers MUST set it.
    engine_version: str

    @abstractmethod
    def render_prompt(
        self, input_content: bytes, input_metadata: dict[str, Any],
    ) -> str:
        """Build the prompt string from input content and metadata.

        Pure function — no side effects, no network calls.
        """

    @abstractmethod
    def call_model(self, prompt: str) -> ModelResponse:
        """Send the prompt to the LLM and return the response.

        May raise on network/provider errors; ``produce`` catches.
        """

    @abstractmethod
    def parse_output(self, raw_output: str) -> dict[str, Any]:
        """Parse raw model output into a schema-conforming dict.

        May raise on malformed output; ``produce`` catches.
        """

    def post_validate(
        self, parsed: dict[str, Any], input_content: bytes,
    ) -> None:
        """Optional hook for producer-specific validation beyond jsonschema.

        Called after ``jsonschema.validate`` succeeds.  Raise to signal
        a failure; ``produce`` catches and converts to ``status='failed'``.
        """
        return

    def produce(
        self,
        input_path: Path,
        input_hash: str,
        config: dict[str, Any],
    ) -> ProducerResult:
        """Orchestrate render → call → parse → validate.

        Never raises; all failures become ``status="failed"``.
        """
        try:
            input_content = input_path.read_bytes()
            input_metadata: dict[str, Any] = {
                "input_hash": input_hash,
                "input_path": str(input_path),
            }

            prompt = self.render_prompt(input_content, input_metadata)
            response = self.call_model(prompt)
            parsed = self.parse_output(response.raw_text)

            jsonschema.validate(parsed, self.output_schema)
            self.post_validate(parsed, input_content)

            content_bytes = canonical_json(parsed).encode("utf-8")
            prompt_hash = hashlib.sha256(
                prompt.encode("utf-8")
            ).hexdigest()

            return ProducerResult(
                status="success",
                content=content_bytes,
                content_type="application/json",
                content_encoding="utf-8",
                error_message=None,
                producer_metadata={
                    "completion": "complete",
                    "model_identity": self.model_identity,
                    "prompt_name": self.prompt_name,
                    "prompt_hash": prompt_hash,
                    "input_tokens": response.input_tokens,
                    "output_tokens": response.output_tokens,
                    "latency_ms": response.latency_ms,
                    "cost_usd": response.cost_usd,
                },
            )
        except jsonschema.ValidationError as e:
            logger.warning(
                "schema validation failed for %s on %s: %s",
                self.name, input_hash[:12], e.message,
            )
            return ProducerResult(
                status="failed",
                content=None,
                content_type=None,
                content_encoding=None,
                error_message=f"schema_validation_failed: {e.message}",
                producer_metadata={},
            )
        except Exception as e:
            logger.warning(
                "transform %s failed on %s: %s",
                self.name, input_hash[:12], e,
            )
            return ProducerResult(
                status="failed",
                content=None,
                content_type=None,
                content_encoding=None,
                error_message=f"{type(e).__name__}: {e}",
                producer_metadata={},
            )
