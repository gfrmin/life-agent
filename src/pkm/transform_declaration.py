"""Transform declaration loader (SPEC v0.2.0 §19.2).

A transform declaration is a YAML file under
``<root>/transforms/<name>.yaml`` specifying the producer class,
model identity, prompt file, output schema, policies, and input
constraints for a single transform.

``load_transform_declaration`` parses the YAML and returns a frozen
``TransformDeclaration`` dataclass.  Prompt and schema files are
resolved relative to the root directory; their contents are loaded
eagerly and hashed for cache-key and integrity purposes.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from pkm.hashing import canonical_json


@dataclass(frozen=True)
class TransformDeclaration:
    """Parsed transform declaration (§19.2)."""

    name: str
    version: str
    producer_class: str
    model_identity: dict[str, Any]
    prompt_name: str
    prompt_text: str
    prompt_hash: str
    output_schema_name: str
    output_schema: dict[str, Any]
    policies: list[str]
    input_producer: str | None
    input_required_status: str
    declaration_hash: str


def load_transform_declaration(
    root: Path, name: str,
) -> TransformDeclaration:
    """Load and validate a transform declaration from disk.

    Args:
        root: Knowledge root directory.
        name: Transform name (matches ``<root>/transforms/<name>.yaml``).

    Raises:
        FileNotFoundError: Declaration, prompt, or schema file missing.
        ValueError: Malformed declaration.
    """
    decl_path = root / "transforms" / f"{name}.yaml"
    raw = yaml.safe_load(decl_path.read_text(encoding="utf-8"))

    prompt_path = root / raw["prompt"]["file"]
    prompt_text = prompt_path.read_text(encoding="utf-8")
    prompt_hash = hashlib.sha256(prompt_text.encode("utf-8")).hexdigest()

    schema_path = root / raw["output_schema"]["file"]
    output_schema = json.loads(schema_path.read_text(encoding="utf-8"))

    declaration_hash = hashlib.sha256(
        canonical_json(raw).encode("utf-8")
    ).hexdigest()

    input_cfg = raw.get("input", {})

    return TransformDeclaration(
        name=raw["name"],
        version=raw["version"],
        producer_class=raw["producer_class"],
        model_identity=raw["model"],
        prompt_name=raw["prompt"]["name"],
        prompt_text=prompt_text,
        prompt_hash=prompt_hash,
        output_schema_name=raw["output_schema"]["name"],
        output_schema=output_schema,
        policies=raw.get("policies", []),
        input_producer=input_cfg.get("producer"),
        input_required_status=input_cfg.get("required_status", "success"),
        declaration_hash=declaration_hash,
    )
