"""Alert rule evaluation helpers for W6.

W9 update: ``AlertManager`` can optionally load rules from a ``ConfigCenter``
via ``from_config_center()``, falling back to hardcoded defaults.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from src.config_center.config_store import ConfigCenter


@dataclass(frozen=True)
class AlertRule:
    """One alert rule definition."""

    name: str
    severity: str
    metric: str
    threshold: float
    comparator: str
    route: str
    description: str


@dataclass
class AlertEvent:
    """One alert evaluation result."""

    name: str
    severity: str
    status: str
    metric: str
    actual_value: float
    threshold: float
    route: str
    description: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dict."""

        return asdict(self)


_DEFAULT_RULES = [
    AlertRule(
        name="low_e2e_success_rate",
        severity="P1",
        metric="e2e_success_rate",
        threshold=0.75,
        comparator="lt",
        route="oncall+owner+war-room",
        description="E2E success rate drops below SLO.",
    ),
    AlertRule(
        name="high_p95_latency",
        severity="P2",
        metric="p95_latency_ms",
        threshold=7.5,
        comparator="gt",
        route="owner+team-channel",
        description="P95 latency exceeds smoke baseline tolerance.",
    ),
    AlertRule(
        name="tool_execution_failures",
        severity="P1",
        metric="failure_buckets.tool_execution_failed",
        threshold=1.0,
        comparator="ge",
        route="oncall+owner+war-room",
        description="Tool execution failures detected.",
    ),
    AlertRule(
        name="rate_limited_burst",
        severity="P2",
        metric="failure_buckets.rate_limited",
        threshold=5.0,
        comparator="ge",
        route="owner+team-channel",
        description="Rate limited events exceed expected noise level.",
    ),
    AlertRule(
        name="token_cost_spike",
        severity="P2",
        metric="cost.total_tokens",
        threshold=240.0,
        comparator="gt",
        route="owner+team-channel",
        description="Token cost exceeds smoke control threshold.",
    ),
]


class AlertManager:
    """Evaluate summaries against alert rules.

    Parameters
    ----------
    rules : list[AlertRule], optional
        Custom rule set.  Defaults to the built-in W6 rules.
    """

    def __init__(self, rules: Optional[List[AlertRule]] = None) -> None:
        self._rules = list(rules) if rules is not None else list(_DEFAULT_RULES)

    @classmethod
    def from_config_center(
        cls,
        config_center: "ConfigCenter",
        namespace: str = "alert_rules",
    ) -> "AlertManager":
        """Create an AlertManager whose rules come from ConfigCenter.

        Each config entry in *namespace* is expected to have a dict value with
        keys: name, severity, metric, threshold, comparator, route, description.
        """
        entries = config_center.list_namespace(namespace)
        rules: List[AlertRule] = []
        for entry in entries:
            v = entry.value
            rules.append(AlertRule(
                name=v["name"],
                severity=v["severity"],
                metric=v["metric"],
                threshold=float(v["threshold"]),
                comparator=v["comparator"],
                route=v["route"],
                description=v.get("description", ""),
            ))
        if not rules:
            return cls()
        return cls(rules=rules)

    def evaluate(self, summary: Dict[str, Any]) -> List[AlertEvent]:
        """Evaluate all rules against one summary."""

        events: List[AlertEvent] = []
        for rule in self._rules:
            actual_value = self._resolve_metric(summary, rule.metric)
            is_firing = self._compare(actual_value, rule.threshold, rule.comparator)
            events.append(
                AlertEvent(
                    name=rule.name,
                    severity=rule.severity,
                    status="firing" if is_firing else "ok",
                    metric=rule.metric,
                    actual_value=actual_value,
                    threshold=rule.threshold,
                    route=rule.route,
                    description=rule.description,
                )
            )
        return events

    def write_json(self, alert_events: List[AlertEvent], output_path: str) -> None:
        """Persist alert evaluation as JSON."""

        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with output_file.open("w", encoding="utf-8") as file_handle:
            json.dump([event.to_dict() for event in alert_events], file_handle, ensure_ascii=False, indent=2)
            file_handle.write("\n")

    def write_markdown(self, alert_events: List[AlertEvent], output_path: str) -> None:
        """Persist alert evaluation as Markdown."""

        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        lines = [
            "# Alert Evaluation",
            "",
            "| Rule | Severity | Status | Metric | Actual | Threshold | Route |",
            "|------|----------|--------|--------|--------|-----------|-------|",
        ]
        for event in alert_events:
            lines.append(
                f"| {event.name} | {event.severity} | {event.status} | {event.metric} | {event.actual_value:.4f} | {event.threshold:.4f} | {event.route} |"
            )
        output_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _resolve_metric(self, summary: Dict[str, Any], metric_path: str) -> float:
        parts = metric_path.split(".")
        current: Any = summary
        for part in parts:
            if not isinstance(current, dict):
                return 0.0
            current = current.get(part, 0.0)
        try:
            return float(current)
        except (TypeError, ValueError):
            return 0.0

    def _compare(self, actual_value: float, threshold: float, comparator: str) -> bool:
        if comparator == "lt":
            return actual_value < threshold
        if comparator == "gt":
            return actual_value > threshold
        if comparator == "ge":
            return actual_value >= threshold
        raise ValueError(f"unsupported comparator: {comparator}")
