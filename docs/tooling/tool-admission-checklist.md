# Tool Admission Checklist

New tools must satisfy all items below before being promoted to AVAILABLE.

## 1. Metadata (Required)

- [ ] `name` — unique, lowercase, snake_case
- [ ] `version` — semantic versioning (MAJOR.MINOR.PATCH)
- [ ] `description` — clear, concise, LLM-consumable
- [ ] `author` — owner/maintainer contact
- [ ] `tags` — at least one classification tag

## 2. Schema (Required)

- [ ] `input_schema` defined with JSON Schema format
- [ ] All required fields listed in `required` array
- [ ] Type annotations for every field
- [ ] `output_schema` defined for downstream consumers

## 3. Permissions (Required)

- [ ] `required_roles` set (default `["public"]`, tighten as needed)
- [ ] `is_sensitive` flag set for destructive/irreversible operations
- [ ] Reviewed against minimum privilege principle

## 4. Quota (Required)

- [ ] QPS limit configured (default: 10/s)
- [ ] Concurrency limit configured (default: 5)
- [ ] Daily quota configured (default: 1000/day)
- [ ] `timeout_seconds` set appropriately

## 5. Resilience (Required)

- [ ] Degradation strategy registered (fallback/cache/handoff)
- [ ] Tool handles timeouts gracefully
- [ ] No unhandled exceptions escape to caller

## 6. Testing (Required)

- [ ] Unit tests for tool logic
- [ ] Schema validation test (valid + invalid inputs)
- [ ] Authorization boundary test
- [ ] Timeout/error path test

## 7. Audit (Required)

- [ ] Tool calls produce audit entries (start/success/failure)
- [ ] No sensitive data in params (use params_hash)
- [ ] Alert-worthy events identified

## 8. Documentation (Recommended)

- [ ] Usage examples in description or separate doc
- [ ] Known limitations documented
- [ ] Changelog for version updates

## Workflow

```
1. Register tool (status=DRAFT)
2. Complete checklist items
3. Run admission tests
4. Peer review
5. Transition to AVAILABLE
6. Monitor via audit dashboard
```

## Change Management

For existing tools:
1. Create new version (don't modify in-place)
2. Test new version in DRAFT
3. Promote new version to AVAILABLE
4. Deprecate old version with reason + replacement reference
5. Monitor for regressions
