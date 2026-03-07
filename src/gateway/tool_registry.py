"""Tool Registry Center - manages tool metadata, lifecycle, and discovery.

Responsibilities:
- Tool registration with versioned metadata (capability, permissions, quota)
- Lifecycle management: draft -> available -> deprecated
- Query interface for tool discovery and capability matching
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class ToolStatus(Enum):
    """Tool lifecycle states."""
    DRAFT = "draft"
    AVAILABLE = "available"
    DEPRECATED = "deprecated"


@dataclass
class QuotaConfig:
    """Tool quota configuration."""
    qps: int = 10
    max_concurrent: int = 5
    daily_limit: int = 1000


@dataclass
class ToolMeta:
    """Tool metadata descriptor."""
    name: str
    version: str
    description: str
    status: ToolStatus = ToolStatus.DRAFT

    # Capability declaration
    input_schema: Dict[str, Any] = field(default_factory=dict)
    output_schema: Dict[str, Any] = field(default_factory=dict)
    capabilities: List[str] = field(default_factory=list)

    # Permission requirements
    required_roles: List[str] = field(default_factory=lambda: ["public"])
    is_sensitive: bool = False

    # Quota limits
    quota: QuotaConfig = field(default_factory=QuotaConfig)

    # Timeout
    timeout_seconds: float = 30.0

    # Metadata
    author: str = ""
    tags: List[str] = field(default_factory=list)
    registered_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    # Deprecation info
    deprecated_reason: str = ""
    replacement_tool: str = ""


class ToolRegistry:
    """Central registry for tool management.

    Provides registration, lifecycle transitions, and query capabilities.
    Stores all versions of a tool for rollback support.
    """

    def __init__(self):
        # {tool_name: {version: ToolMeta}}
        self._tools: Dict[str, Dict[str, ToolMeta]] = {}
        # {tool_name: current_version}
        self._active_versions: Dict[str, str] = {}

    def register(self, meta: ToolMeta) -> ToolMeta:
        """Register a new tool or a new version of an existing tool.

        Raises:
            ValueError: If the same name+version already exists.
        """
        if meta.name in self._tools and meta.version in self._tools[meta.name]:
            raise ValueError(
                f"Tool '{meta.name}' version '{meta.version}' already registered. "
                "Use a new version string for updates."
            )

        if meta.name not in self._tools:
            self._tools[meta.name] = {}

        self._tools[meta.name][meta.version] = meta

        # Auto-set active version if first registration or status is available
        if meta.name not in self._active_versions:
            self._active_versions[meta.name] = meta.version
        if meta.status == ToolStatus.AVAILABLE:
            self._active_versions[meta.name] = meta.version

        return meta

    def get(self, name: str, version: Optional[str] = None) -> Optional[ToolMeta]:
        """Get tool metadata. Returns active version if version not specified."""
        if name not in self._tools:
            return None
        if version:
            return self._tools[name].get(version)
        active_ver = self._active_versions.get(name)
        if active_ver:
            return self._tools[name].get(active_ver)
        return None

    def get_all_versions(self, name: str) -> List[ToolMeta]:
        """Get all versions of a tool, sorted by registration time."""
        if name not in self._tools:
            return []
        versions = list(self._tools[name].values())
        versions.sort(key=lambda m: m.registered_at)
        return versions

    def transition(self, name: str, version: str, target_status: ToolStatus,
                   reason: str = "", replacement: str = "") -> ToolMeta:
        """Transition a tool to a new lifecycle state.

        Valid transitions:
            draft -> available
            available -> deprecated
            draft -> deprecated (skip availability)

        Raises:
            ValueError: If tool not found or transition is invalid.
        """
        meta = self.get(name, version)
        if not meta:
            raise ValueError(f"Tool '{name}' version '{version}' not found.")

        valid_transitions = {
            ToolStatus.DRAFT: {ToolStatus.AVAILABLE, ToolStatus.DEPRECATED},
            ToolStatus.AVAILABLE: {ToolStatus.DEPRECATED},
            ToolStatus.DEPRECATED: set(),
        }

        if target_status not in valid_transitions[meta.status]:
            raise ValueError(
                f"Invalid transition: {meta.status.value} -> {target_status.value}. "
                f"Allowed: {[s.value for s in valid_transitions[meta.status]]}"
            )

        meta.status = target_status
        meta.updated_at = time.time()

        if target_status == ToolStatus.AVAILABLE:
            self._active_versions[name] = version

        if target_status == ToolStatus.DEPRECATED:
            meta.deprecated_reason = reason
            meta.replacement_tool = replacement
            # If deprecating the active version, try to find another available version
            if self._active_versions.get(name) == version:
                self._active_versions.pop(name, None)
                for v_meta in reversed(self.get_all_versions(name)):
                    if v_meta.status == ToolStatus.AVAILABLE and v_meta.version != version:
                        self._active_versions[name] = v_meta.version
                        break

        return meta

    def list_tools(self, status: Optional[ToolStatus] = None,
                   tag: Optional[str] = None,
                   capability: Optional[str] = None) -> List[ToolMeta]:
        """Query tools by filters. Returns active versions only."""
        results = []
        for name in self._tools:
            meta = self.get(name)
            if not meta:
                continue
            if status and meta.status != status:
                continue
            if tag and tag not in meta.tags:
                continue
            if capability and capability not in meta.capabilities:
                continue
            results.append(meta)
        return results

    def unregister(self, name: str) -> bool:
        """Remove all versions of a tool entirely.

        Returns True if the tool existed and was removed.
        """
        if name not in self._tools:
            return False
        del self._tools[name]
        self._active_versions.pop(name, None)
        return True

    @property
    def tool_count(self) -> int:
        """Number of unique registered tools."""
        return len(self._tools)

    def export_catalog(self) -> List[Dict[str, Any]]:
        """Export a summary catalog of all active tools for LLM consumption."""
        catalog = []
        for meta in self.list_tools():
            catalog.append({
                "name": meta.name,
                "version": meta.version,
                "description": meta.description,
                "status": meta.status.value,
                "capabilities": meta.capabilities,
                "input_schema": meta.input_schema,
                "required_roles": meta.required_roles,
                "is_sensitive": meta.is_sensitive,
            })
        return catalog
