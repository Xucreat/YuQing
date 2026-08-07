# MediaCrawler Filter Integration Implementation

## 1. Modified files

| File | Reason |
| --- | --- |
| `backend/app/collectors/media_crawler_platform_collector.py` | Shared MediaCrawler search-scope resolution and post-normalizer admission gate for Weibo and XHS. |
| `backend/app/collectors/mediacrawler_normalizers.py` | Shared scoped keyword resolution and social-platform filter-text construction. |
| `backend/app/collectors/mediacrawler_runner.py` | Persist the MediaCrawler-only `filter_skipped` metrics counter. |
| `backend/app/collectors/source_config.py` | Normalize `region_only` / `topic_only` compatibility aliases to the existing `region` / `topic` helper vocabulary. Existing ordinary values and behavior remain unchanged. |
| `backend/tests/test_media_crawler_filter_integration.py` | Covers keyword scopes, filter modes, social metadata, and shared Weibo/XHS behavior. |
| `docs/Phase_MediaCrawler_Filter_Integration_Audit.md` | Phase 1 read-only audit conclusion. |

No database migration, Opinion schema change, Scheduler change, or
`CollectorService` change was made.

## 2. Filter chain

### Before

```text
config_json
  -> resolve_effective_keywords()
  -> all datasource/runtime/global keywords
  -> MediaCrawler search
  -> normalize
  -> direct item return
  -> CollectorService creates Opinion
```

`filter_mode` and `keyword_scope` were only configuration whitelist fields.

### After

```text
config_json
  -> read keyword_scope
  -> apply_keyword_scope(region_kw, topic_kw)
  -> scoped search keyword list
  -> MediaCrawler search
  -> normalize
  -> build filter_text from title/content/desc/tags/hashtags/topic/comments
  -> matches_region_topic(filter_text, scoped region/topic keywords, filter_mode)
  -> admitted item return
  -> CollectorService creates Opinion
```

When `filter_mode` is not configured, the post-normalizer admission gate is
disabled, preserving the old full-ingest behavior. When `keyword_scope` is
not configured, the old keyword precedence and round-robin override behavior
are preserved.

## 3. Implementation details

### Search keyword scope

`MediaCrawlerPlatformCollector.fetch()` now:

1. reads `DataSourceConfig.keyword_scope()`;
2. applies the existing `apply_keyword_scope()` to the categorized
   `region_kw` and `topic_kw` lists;
3. uses the scoped union for `resolve_effective_keywords()`;
4. ignores the preselected one-word round-robin override only when an
   explicit keyword scope is configured, so a topic word cannot bypass
   `region_only`.

The existing datasource-local keyword precedence remains:

```text
config_json.keywords
  > runtime keywords
  > global monitoring keywords
```

The explicit aliases `region_only` and `topic_only` normalize to the
existing helper values `region` and `topic`.

### Admission filtering

Filtering occurs in `_read_jsonl()` immediately after the platform normalizer
returns a unified item and before de-duplication/return to the service.

The gate calls the existing matcher:

```python
matches_region_topic(
    filter_text,
    region_kw or [],
    topic_kw or [],
    match_mode=filter_mode,
)
```

No new matching algorithm or database field was introduced.

### Filter text

The shared builder includes normalized `title` and `content`, plus raw
platform fields:

- `title`
- `content`
- `desc`
- `description`
- `text`
- `hashtags`
- `tags`
- `topic`
- `comments`

Nested lists and mappings are flattened to text. The extra text is used only
for filtering and is not persisted in `Opinion`.

### Skipped metrics

Rejected normalized rows are counted in:

- `collector.last_filter_skipped`
- the MediaCrawler run log as `filter_skipped=...`
- `metrics.json` as `filter_skipped`

This avoids changing `CollectorRun`, `Opinion`, or the service flow.

## 4. Test results

Passed:

```text
pytest -q tests/test_media_crawler_filter_integration.py \
  tests/test_media_crawler_2d.py \
  tests/test_media_crawler_2e_fix.py \
  tests/test_media_crawler_2f_fix.py \
  tests/test_media_crawler_adapter.py \
  tests/test_media_crawler_platform_1.py \
  tests/test_media_crawler_xhs_platform.py
54 passed, 1 warning
```

The new integration test file alone passed:

```text
7 passed, 1 warning
```

Compile and whitespace checks passed:

```text
python -m compileall -q ...
git diff --check
```

An additional existing XHS registration-contract test remains failing
independently of this change because
`build_xhs_mediacrawler_data_source_payload()` currently returns
`scope_region_codes=None` while the existing test expects `"131028"`.
That registration code was not modified.

An ordinary-collector regression command was attempted but exceeded the
120-second test timeout without producing a failure assertion. It should be
rerun in the project’s normal CI environment.

## 5. Risk notes

- A configured scope with no categorized region/topic keyword lists produces
  an empty search list; production `CollectorService` already supplies both
  grouped lists, but direct callers should pass them when using a scope.
- `filter_mode` is intentionally opt-in for MediaCrawler. Existing `{}` or
  configs without `filter_mode` retain full ingestion.
- Filtering occurs after runner `max_items` bounding, so a restrictive mode
  can return fewer than `max_items`; this is expected and preserves the
  upstream runner contract.
- The new `filter_skipped` metric is runner-artifact telemetry only. The
  database `CollectorRun.admission_filtered` field remains untouched because
  changing `CollectorService` was explicitly prohibited.
- Social metadata may contain nested or noisy values. The builder flattens
  them for matching but does not alter stored content.
