"""Data models for the configuration center."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class ConfigType(Enum):
    """Supported configuration types."""

    EXPERIMENT = "experiment"
    ALERT_RULE = "alert_rule"
    TENANT_POLICY = "tenant_policy"
    GATEWAY = "gateway"
    FEATURE_FLAG = "feature_flag"


@dataclass
class ConfigEntry:
    """One configuration entry with versioning metadata."""

    namespace: str
    key: str
    value: Any
    version: int = 0
    config_type: str = "feature_flag"
    updated_at: float = 0.0
    description: str = ""


@dataclass
class ConfigNamespace:
    """Logical grouping of config entries."""

    name: str
    description: str = ""
    entries: dict = field(default_factory=dict)


@dataclass
class WatchEvent:
    """Event emitted when a config key changes."""

    namespace: str
    key: str
    old_value: Any
    new_value: Any
    old_version: int
    new_version: int
    event_type: str = "updated"
