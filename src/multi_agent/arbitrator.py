"""Conflict arbitration for W7 multi-agent collaboration."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class ArbitrationCandidate:
    """One candidate result participating in arbitration."""

    role: str
    result: Any
    confidence: float
    priority: int
    evidence: List[str] = field(default_factory=list)


@dataclass
class ArbitrationDecision:
    """Final arbitration result."""

    status: str
    selected_role: str
    result: Any
    rationale: str
    evidence_chain: List[str]


class Arbitrator:
    """Resolve conflicting results with deterministic policy."""

    def resolve(self, candidates: List[ArbitrationCandidate]) -> ArbitrationDecision:
        """Resolve one set of candidates."""

        if not candidates:
            raise ValueError("candidates must not be empty")
        ranked = sorted(
            candidates,
            key=lambda item: (item.priority, -item.confidence, item.role),
        )
        best = ranked[0]
        if len(ranked) > 1 and self._needs_human(best, ranked[1]):
            return ArbitrationDecision(
                status="needs_human",
                selected_role=best.role,
                result=best.result,
                rationale="top candidates are too close; human fallback required",
                evidence_chain=self._build_evidence_chain(ranked),
            )
        return ArbitrationDecision(
            status="resolved",
            selected_role=best.role,
            result=best.result,
            rationale="selected by priority first, then confidence",
            evidence_chain=self._build_evidence_chain(ranked),
        )

    def _needs_human(
        self,
        best: ArbitrationCandidate,
        second: ArbitrationCandidate,
    ) -> bool:
        same_priority = best.priority == second.priority
        confidence_gap = abs(best.confidence - second.confidence)
        conflicting_result = best.result != second.result
        return same_priority and conflicting_result and confidence_gap < 0.1

    def _build_evidence_chain(
        self,
        ranked: List[ArbitrationCandidate],
    ) -> List[str]:
        chain: List[str] = []
        for candidate in ranked:
            evidence_summary = "; ".join(candidate.evidence) if candidate.evidence else "no evidence"
            chain.append(
                f"role={candidate.role}, priority={candidate.priority}, confidence={candidate.confidence:.2f}, evidence={evidence_summary}"
            )
        return chain
