# Tool Lifecycle Management

## Lifecycle States

```
 [DRAFT] ──publish──> [AVAILABLE] ──deprecate──> [DEPRECATED]
    │                                                  ^
    └──────────── skip (fast deprecate) ──────────────┘
```

### DRAFT
- Tool is registered but not yet available for agent use.
- Used for development and testing.
- Not returned by default queries unless explicitly requested.

### AVAILABLE
- Tool is active and can be invoked by agents.
- Only one version per tool name is "active" at a time.
- Publishing a new version auto-promotes it to active.

### DEPRECATED
- Tool should no longer be used.
- Existing in-flight calls are allowed to complete.
- Must specify `deprecated_reason` and optionally `replacement_tool`.
- Registry auto-falls back to the latest available version if one exists.

## Tool Metadata

Each registered tool carries:

| Field | Type | Description |
|-------|------|-------------|
| name | str | Unique tool identifier |
| version | str | Semantic version (e.g., "1.0.0") |
| description | str | Human/LLM-readable description |
| status | ToolStatus | Current lifecycle state |
| input_schema | dict | JSON Schema for input validation |
| output_schema | dict | JSON Schema for output validation |
| capabilities | list[str] | Declared capability tags |
| required_roles | list[str] | Minimum roles needed to invoke |
| is_sensitive | bool | Whether invocation needs confirmation |
| quota | QuotaConfig | QPS / concurrency / daily limits |
| timeout_seconds | float | Max execution time |
| author | str | Owner/maintainer |
| tags | list[str] | Classification tags |

## Version Management

- All versions of a tool are retained for rollback.
- `get(name)` returns the active version; `get(name, version)` returns a specific one.
- `get_all_versions(name)` lists all versions sorted by registration time.
- Deprecating the active version triggers auto-fallback to the latest available version.

## Registration Flow

1. Create `ToolMeta` with status=DRAFT.
2. Register via `registry.register(meta)`.
3. Test the tool in draft state.
4. Transition to AVAILABLE: `registry.transition(name, version, ToolStatus.AVAILABLE)`.
5. Tool is now discoverable and invocable.

## Deprecation Flow

1. Register replacement tool (if any) and publish it.
2. Deprecate old version: `registry.transition(name, version, ToolStatus.DEPRECATED, reason="...", replacement="...")`.
3. Active version auto-switches to replacement if available.

## LLM Catalog Export

`registry.export_catalog()` produces a minimal JSON list for LLM tool-use prompting:

```json
[
  {
    "name": "web_search",
    "version": "1.2.0",
    "description": "Search the web for current information",
    "status": "available",
    "capabilities": ["search", "web"],
    "input_schema": {"query": {"type": "string"}},
    "required_roles": ["public"],
    "is_sensitive": false
  }
]
```
