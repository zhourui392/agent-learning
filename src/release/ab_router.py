"""Deterministic A/B routing helpers for W8 release governance.

W9 update: ``AbRouter.from_config_center()`` loads experiment configs from
the configuration center, enabling dynamic updates without restarts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from src.config_center.config_store import ConfigCenter


@dataclass(frozen=True)
class VariantAllocation:
    """One experiment variant with traffic allocation."""

    name: str
    percentage: float


@dataclass(frozen=True)
class MetricGuardrail:
    """One experiment safety rule."""

    metric: str
    comparator: str
    threshold: float
    action: str = "stop_experiment"


@dataclass(frozen=True)
class ExperimentConfig:
    """Experiment routing configuration."""

    experiment_id: str
    default_variant: str
    variants: List[VariantAllocation]
    enabled: bool = True
    salt: str = "default"
    allow_override: bool = True
    guardrails: List[MetricGuardrail] = field(default_factory=list)


@dataclass(frozen=True)
class RoutingDecision:
    """Final routing result for one subject."""

    experiment_id: str
    subject_key: str
    variant: str
    bucket: float
    reason: str


@dataclass(frozen=True)
class GuardrailHit:
    """One triggered safety rule."""

    metric: str
    comparator: str
    actual_value: float
    threshold: float
    action: str


@dataclass(frozen=True)
class ExperimentSafetyDecision:
    """Experiment safety evaluation result."""

    status: str
    should_stop: bool
    hits: List[GuardrailHit]


class AbRouter:
    """Provide deterministic routing and guardrail evaluation."""

    def route(
        self,
        config: ExperimentConfig,
        subject_key: str,
        override_variant: str | None = None,
    ) -> RoutingDecision:
        """Route one subject to a stable experiment variant."""

        self._validate_config(config)

        if not config.enabled:
            return RoutingDecision(
                experiment_id=config.experiment_id,
                subject_key=subject_key,
                variant=config.default_variant,
                bucket=0.0,
                reason="experiment_disabled",
            )

        if override_variant is not None:
            return self._build_override_decision(config, subject_key, override_variant)

        bucket = self._calculate_bucket(config.experiment_id, config.salt, subject_key)
        selected_variant = self._select_variant(config.variants, bucket)
        return RoutingDecision(
            experiment_id=config.experiment_id,
            subject_key=subject_key,
            variant=selected_variant,
            bucket=bucket,
            reason="bucket_assignment",
        )

    def evaluate_guardrails(
        self,
        config: ExperimentConfig,
        metrics: Dict[str, Any],
    ) -> ExperimentSafetyDecision:
        """Check whether one experiment should be stopped."""

        hits: List[GuardrailHit] = []
        for rule in config.guardrails:
            actual_value = self._resolve_metric(metrics, rule.metric)
            if not self._compare(actual_value, rule.threshold, rule.comparator):
                continue
            hits.append(
                GuardrailHit(
                    metric=rule.metric,
                    comparator=rule.comparator,
                    actual_value=actual_value,
                    threshold=rule.threshold,
                    action=rule.action,
                )
            )

        should_stop = any(hit.action == "stop_experiment" for hit in hits)
        status = self._build_safety_status(hits, should_stop)
        return ExperimentSafetyDecision(status=status, should_stop=should_stop, hits=hits)

    def _build_override_decision(
        self,
        config: ExperimentConfig,
        subject_key: str,
        override_variant: str,
    ) -> RoutingDecision:
        if not config.allow_override:
            raise ValueError("override is disabled for this experiment")

        variant_names = {variant.name for variant in config.variants}
        if override_variant not in variant_names:
            raise ValueError(f"unknown override variant: {override_variant}")

        return RoutingDecision(
            experiment_id=config.experiment_id,
            subject_key=subject_key,
            variant=override_variant,
            bucket=0.0,
            reason="manual_override",
        )

    def _validate_config(self, config: ExperimentConfig) -> None:
        if not config.variants:
            raise ValueError("experiment variants cannot be empty")

        variant_names = [variant.name for variant in config.variants]
        if config.default_variant not in variant_names:
            raise ValueError("default variant must exist in variants")

        total_percentage = sum(variant.percentage for variant in config.variants)
        if abs(total_percentage - 100.0) > 1e-6:
            raise ValueError("variant percentages must sum to 100")

        if len(set(variant_names)) != len(variant_names):
            raise ValueError("variant names must be unique")

    def _calculate_bucket(self, experiment_id: str, salt: str, subject_key: str) -> float:
        digest = sha256(f"{experiment_id}:{salt}:{subject_key}".encode("utf-8")).hexdigest()
        bucket_value = int(digest[:8], 16) % 10_000
        return bucket_value / 100

    def _select_variant(self, variants: List[VariantAllocation], bucket: float) -> str:
        current_boundary = 0.0
        for variant in variants:
            current_boundary += variant.percentage
            if bucket < current_boundary:
                return variant.name
        return variants[-1].name

    def _resolve_metric(self, metrics: Dict[str, Any], metric_path: str) -> float:
        current: Any = metrics
        for segment in metric_path.split("."):
            if not isinstance(current, dict):
                return 0.0
            current = current.get(segment, 0.0)

        try:
            return float(current)
        except (TypeError, ValueError):
            return 0.0

    def _compare(self, actual_value: float, threshold: float, comparator: str) -> bool:
        if comparator == "lt":
            return actual_value < threshold
        if comparator == "le":
            return actual_value <= threshold
        if comparator == "gt":
            return actual_value > threshold
        if comparator == "ge":
            return actual_value >= threshold
        raise ValueError(f"unsupported comparator: {comparator}")

    @staticmethod
    def from_config_center(
        config_center: "ConfigCenter",
        namespace: str = "experiments",
    ) -> Dict[str, ExperimentConfig]:
        """Load all experiment configs from ConfigCenter.

        Each config entry value should be a dict with keys matching
        ``ExperimentConfig`` fields.  Returns ``{experiment_id: config}``.
        """
        entries = config_center.list_namespace(namespace)
        configs: Dict[str, ExperimentConfig] = {}
        for entry in entries:
            v = entry.value
            variants = [
                VariantAllocation(name=va["name"], percentage=float(va["percentage"]))
                for va in v.get("variants", [])
            ]
            guardrails = [
                MetricGuardrail(
                    metric=g["metric"],
                    comparator=g["comparator"],
                    threshold=float(g["threshold"]),
                    action=g.get("action", "stop_experiment"),
                )
                for g in v.get("guardrails", [])
            ]
            config = ExperimentConfig(
                experiment_id=v["experiment_id"],
                default_variant=v["default_variant"],
                variants=variants,
                enabled=v.get("enabled", True),
                salt=v.get("salt", "default"),
                allow_override=v.get("allow_override", True),
                guardrails=guardrails,
            )
            configs[config.experiment_id] = config
        return configs

    def _build_safety_status(self, hits: List[GuardrailHit], should_stop: bool) -> str:
        if should_stop:
            return "stop"
        if hits:
            return "warn"
        return "ok"
