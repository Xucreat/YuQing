# National Region Sentinel Audit

## Result

PASS

Database: READ ONLY

The audit target is `regions.code='000000'`. The existing Phase National-Mode
read-only baseline confirms one sentinel row is present and uniquely identified
by that code. The audit script rechecks existence, uniqueness, and the
non-empty `id`, `code`, and `name` fields without changing data.

The current `regions` schema intentionally has no `enabled` column. The audit
reports `enabled=NOT_APPLICABLE_SCHEMA_FIELD_ABSENT`; adding an enabled field
would violate this phase's no-schema-change boundary and is not required for
sentinel identity.

## Query Summary

```text
SELECT id, code, name
FROM regions
WHERE code = '000000'
```

Recorded result: exactly one row (`id=24`, `code=000000`, `name=全国`), with a
valid id and non-empty national name. The script also reports the row count so
duplicate sentinels fail closed.

## Safety

- Database: READ ONLY
- Writes performed: NONE
- INSERT / UPDATE / DELETE: NOT USED
- Migration: UNCHANGED
- Schema: UNCHANGED

The script is `backend/scripts/check_national_region_sentinel.py` and exits
with `0` only when exactly one valid sentinel row is returned.
