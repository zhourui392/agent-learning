"""Tests for tool registry center."""

import pytest

from src.gateway.tool_registry import (
    QuotaConfig,
    ToolMeta,
    ToolRegistry,
    ToolStatus,
)


@pytest.fixture
def registry():
    return ToolRegistry()


def _make_tool(name="web_search", version="1.0.0", status=ToolStatus.DRAFT, **kwargs):
    return ToolMeta(name=name, version=version, description=f"{name} v{version}",
                    status=status, **kwargs)


class TestRegistration:
    def test_register_new_tool(self, registry):
        meta = _make_tool()
        result = registry.register(meta)
        assert result.name == "web_search"
        assert registry.tool_count == 1

    def test_register_duplicate_raises(self, registry):
        registry.register(_make_tool())
        with pytest.raises(ValueError, match="already registered"):
            registry.register(_make_tool())

    def test_register_new_version(self, registry):
        registry.register(_make_tool(version="1.0.0"))
        registry.register(_make_tool(version="2.0.0"))
        assert registry.tool_count == 1
        assert len(registry.get_all_versions("web_search")) == 2

    def test_unregister(self, registry):
        registry.register(_make_tool())
        assert registry.unregister("web_search") is True
        assert registry.tool_count == 0
        assert registry.unregister("web_search") is False


class TestQuery:
    def test_get_active_version(self, registry):
        registry.register(_make_tool(version="1.0.0"))
        registry.register(_make_tool(version="2.0.0", status=ToolStatus.AVAILABLE))
        meta = registry.get("web_search")
        assert meta.version == "2.0.0"

    def test_get_specific_version(self, registry):
        registry.register(_make_tool(version="1.0.0"))
        registry.register(_make_tool(version="2.0.0"))
        meta = registry.get("web_search", "1.0.0")
        assert meta.version == "1.0.0"

    def test_get_nonexistent(self, registry):
        assert registry.get("nonexistent") is None

    def test_list_by_status(self, registry):
        registry.register(_make_tool(name="a", status=ToolStatus.AVAILABLE))
        registry.register(_make_tool(name="b", status=ToolStatus.DRAFT))
        available = registry.list_tools(status=ToolStatus.AVAILABLE)
        assert len(available) == 1
        assert available[0].name == "a"

    def test_list_by_tag(self, registry):
        registry.register(_make_tool(name="a", tags=["search"]))
        registry.register(_make_tool(name="b", tags=["code"]))
        results = registry.list_tools(tag="search")
        assert len(results) == 1

    def test_list_by_capability(self, registry):
        registry.register(_make_tool(name="a", capabilities=["web"]))
        registry.register(_make_tool(name="b", capabilities=["file"]))
        results = registry.list_tools(capability="web")
        assert len(results) == 1


class TestLifecycle:
    def test_draft_to_available(self, registry):
        registry.register(_make_tool())
        meta = registry.transition("web_search", "1.0.0", ToolStatus.AVAILABLE)
        assert meta.status == ToolStatus.AVAILABLE

    def test_available_to_deprecated(self, registry):
        registry.register(_make_tool(status=ToolStatus.AVAILABLE))
        meta = registry.transition("web_search", "1.0.0", ToolStatus.DEPRECATED,
                                   reason="outdated", replacement="web_search_v2")
        assert meta.status == ToolStatus.DEPRECATED
        assert meta.deprecated_reason == "outdated"
        assert meta.replacement_tool == "web_search_v2"

    def test_invalid_transition_raises(self, registry):
        registry.register(_make_tool(status=ToolStatus.AVAILABLE))
        registry.transition("web_search", "1.0.0", ToolStatus.DEPRECATED)
        with pytest.raises(ValueError, match="Invalid transition"):
            registry.transition("web_search", "1.0.0", ToolStatus.AVAILABLE)

    def test_deprecate_active_falls_back(self, registry):
        registry.register(_make_tool(version="1.0.0", status=ToolStatus.AVAILABLE))
        registry.register(_make_tool(version="2.0.0", status=ToolStatus.AVAILABLE))
        registry.transition("web_search", "2.0.0", ToolStatus.DEPRECATED)
        active = registry.get("web_search")
        assert active.version == "1.0.0"

    def test_transition_nonexistent_raises(self, registry):
        with pytest.raises(ValueError, match="not found"):
            registry.transition("nope", "1.0.0", ToolStatus.AVAILABLE)


class TestCatalogExport:
    def test_export_catalog(self, registry):
        registry.register(_make_tool(status=ToolStatus.AVAILABLE,
                                     capabilities=["search"],
                                     input_schema={"query": {"type": "string"}}))
        catalog = registry.export_catalog()
        assert len(catalog) == 1
        entry = catalog[0]
        assert entry["name"] == "web_search"
        assert entry["status"] == "available"
        assert "capabilities" in entry
