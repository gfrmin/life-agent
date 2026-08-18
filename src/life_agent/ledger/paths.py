"""The legacy store paths — one immutable object so the harness, the migration writer and
the seeds all name the same files, and a seed can redirect a *copy* (design §9)."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from life_agent.core import config


@dataclass(frozen=True)
class Paths:
    tasks_ledger: Path
    trips_ledger: Path
    outcomes: Path
    decisions: Path
    reactions: Path
    claude_verdicts: Path
    gather_outcomes: Path
    corrections: Path
    elicitations: Path
    utility_model: Path
    labels: Path
    pkm_root: Path | None
    # A10 reads the decision-referenced artefacts from here (defaults to pkm_root); the
    # substitute-artifact seed redirects ONLY this, so A11/A12 keep reading the real root.
    answers_root: Path | None = None
    # A2's stamp hashes the LEGACY ledger's bytes (R1). Defaults to ``tasks_ledger``; the
    # stream adapter (Phase 3) points ``tasks_ledger`` at the materialised stream and keeps
    # this at the dual-written legacy file.
    state_sha_source: Path | None = None

    @classmethod
    def from_config(cls, *, resolve_pkm: bool = True) -> Paths:
        """The configured legacy stores. ``resolve_pkm=False`` skips the ``PKM_CONFIG`` YAML
        read (``pkm_root=None``) — the live mirror needs only the JSONL paths and must not pay
        for a file read per call."""
        return cls(
            tasks_ledger=config.TASKS_LEDGER, trips_ledger=config.TRIPS_LEDGER,
            outcomes=config.OUTCOMES_LOG, decisions=config.DECISIONS_LOG,
            reactions=config.REACTIONS_LOG, claude_verdicts=config.CLAUDE_VERDICTS_LOG,
            gather_outcomes=config.GATHER_OUTCOMES_LOG,
            corrections=config.OUTCOMES_LOG.parent / "corrections.jsonl",
            elicitations=config.UTILITY_ELICITATIONS, utility_model=config.UTILITY_MODEL,
            labels=config.KB / "eval" / "labels.jsonl",
            pkm_root=config.pkm_root() if resolve_pkm else None,
        )

    def legacy_files(self) -> dict[str, Path]:
        """The ten JSONL legacy stores by ``source_id`` (pkm's two are directory-shaped)."""
        return {
            "act.tasks": self.tasks_ledger, "act.trips": self.trips_ledger,
            "calibration.outcomes": self.outcomes, "calibration.decisions": self.decisions,
            "calibration.reactions": self.reactions,
            "calibration.claude_verdicts": self.claude_verdicts,
            "calibration.gather_outcomes": self.gather_outcomes,
            "calibration.corrections": self.corrections,
            "utility.elicitations": self.elicitations, "eval.labels": self.labels,
        }

    def legacy_file(self, source_id: str) -> Path:
        return self.legacy_files()[source_id]
