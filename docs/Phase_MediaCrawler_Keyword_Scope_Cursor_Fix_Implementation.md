# MediaCrawler Keyword Scope Cursor Fix Implementation

## 1. Modified files

| File | Change |
| --- | --- |
| `backend/app/collectors/service.py` | Extended the MediaCrawler-only keyword-turn helper to apply `keyword_scope` before using the persisted `keyword_cursor`. |
| `backend/app/collectors/media_crawler_platform_collector.py` | Always honors the selected `keyword_override`; skips the runner when the scoped pool is empty. |
| `backend/tests/test_media_crawler_filter_integration.py` | Added shared Weibo/XHS tests for scope pools, cursor order, single-keyword search, empty pools, max_items, filter_mode, and social metadata. |
| `docs/Phase_MediaCrawler_Keyword_Scope_Cursor_Fix_Implementation.md` | This implementation report. |

Existing `source_config`, normalizer, runner metrics, and filter implementations
from the preceding MediaCrawler integration were reused. No database schema,
Opinion schema, Scheduler, or CollectorService Opinion workflow was changed.

## 2. Current problem

Before this fix, the MediaCrawler-specific helper selected a keyword from the
complete effective keyword list:

```text
all effective keywords
  -> keyword_cursor selects one keyword
  -> collector.fetch(keyword_override=selected)
```

When `keyword_scope` was configured, the collector then ignored that selected
keyword and regenerated the complete scoped list. This made the scope affect
the search list, but not the cursor pool:

```text
cursor selects one keyword
  -> keyword_scope is applied later
  -> multiple scoped keywords are sent together
```

Consequences included uneven keyword coverage and a single `max_items` bound
being consumed by a multi-keyword search.

## 3. Before / after

### Before

```text
all enabled/effective keywords
  -> keyword_cursor selects one keyword
  -> keyword_scope configured
  -> selected keyword is ignored
  -> all scoped keywords search together
  -> normalize
  -> existing MediaCrawler filter gate
  -> CollectorService
  -> Opinion
```

### After

```text
all enabled/effective keywords
  -> apply_keyword_scope(region_kw, topic_kw)
  -> scoped keyword pool
  -> persisted keyword_cursor selects one keyword
  -> MediaCrawler searches one keyword
  -> max_items bounds this one search
  -> normalize
  -> build filter_text
  -> filter_mode / matches_region_topic()
  -> CollectorService
  -> Opinion
```

## 4. keyword_scope and keyword_cursor

The scope values use the existing helper vocabulary and compatibility aliases:

| Configuration | Canonical meaning | Cursor pool |
| --- | --- | --- |
| `region` / `region_only` | region keywords only | `region_kw` |
| `topic` / `topic_only` | topic keywords only | `topic_kw` |
| `region_topic` | both groups | `region_kw + topic_kw` |
| not configured | legacy behavior | all effective keywords |

For configured scopes, the helper first applies
`apply_keyword_scope()`, then normalizes and de-duplicates the resulting pool,
then uses the existing persisted `DataSource.keyword_cursor`.

Example with cursor reset to zero:

```text
region_topic pool = [大厂, 廊坊, 火灾, 事故]

round 1 -> 大厂
round 2 -> 廊坊
round 3 -> 火灾
round 4 -> 事故
round 5 -> 大厂
```

The production cursor is not reset between runs. Tests reset it only when a
deterministic sequence is required.

If the scoped pool is empty:

- the helper returns no selected keyword;
- the cursor is not advanced;
- the collector does not start MediaCrawler;
- a warning identifies the empty scoped pool.

If no database source row is available, the existing manual/injected fallback
is retained. Unscoped calls preserve the previous all-keyword return behavior;
scoped calls select the first scoped keyword without persistence.

## 5. max_items

`max_items` remains the runner bound for one invocation. Since the corrected
flow sends one selected keyword per invocation:

```text
max_items=20
  -> selected keyword search returns at most 20 raw rows
  -> normalizer and filter_mode may reduce the final Opinion candidates
```

There is no multi-keyword accumulation such as `20 + 20` within one round.

## 6. filter_mode admission

The existing shared MediaCrawler post-normalizer gate remains unchanged:

```text
raw row
  -> WeiboNormalizer / XhsNormalizer
  -> filter_text
  -> matches_region_topic(..., match_mode=filter_mode)
  -> admitted item or skip
```

`filter_text` continues to include normalized title/content and supported
social metadata such as `desc`, `hashtags`, `tags`, `topic`, and `comments`.
Rejected rows continue to be counted as `filter_skipped` in MediaCrawler
metrics. No database field is added.

## 7. Test results

Focused scope/cursor/filter tests:

```text
18 passed, 1 warning
```

Weibo/XHS platform regression tests:

```text
17 passed, 1 warning
```

Compile and whitespace checks:

```text
python -m compileall -q ...
git diff --check
```

The combined MediaCrawler selection included one pre-existing failure in
`test_xhs_registration_payload_is_formal_and_disabled_by_default`:
the current registration payload returns `scope_region_codes=None`, while the
existing test expects `"131028"`. The registration implementation was not
changed by this fix.

Broader test commands exceeded the 120-second timeout without producing a
failure assertion. The focused tests above completed successfully.

## 8. Compatibility and risk

- Weibo and XHS remain on the same platform-neutral keyword selection and
  filtering path.
- `filter_mode` admission remains enabled where configured.
- `config_json={}` retains the previous all-keyword and cursor behavior.
- Unconfigured `keyword_scope` does not alter the legacy keyword pool.
- Ordinary collectors are not changed.
- No database migration or new cursor field is introduced.
- An empty configured scope now intentionally produces no runner invocation;
  it does not fall back to all keywords.
- Manual/injected collectors without a database cursor cannot persist cursor
  progress; their existing fallback behavior remains in place.
