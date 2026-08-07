# MediaCrawler Filter Integration Audit

## Scope

This audit is read-only. It covers the MediaCrawler collector path, the
Weibo compatibility facade, the XHS platform contract, the normalizer layer,
and the existing ordinary-collector filtering implementation.

## Findings

### 1. MediaCrawler public/shared base

The shared collector is:

- `backend/app/collectors/media_crawler_platform_collector.py`
  - `MediaCrawlerPlatformCollector`

The platform-specific Weibo class is a compatibility facade:

- `backend/app/collectors/media_crawler_weibo_collector.py`
  - `MediaCrawlerWeiboCollector` subclasses the shared collector.

There is no separate `media_crawler_xhs_collector.py` in the current
workspace. XHS is assembled through the generic
`MediaCrawlerPlatformCollector` with `XHS_PLATFORM_SPEC`.

### 2. Search keyword generation

The current keyword path is:

```text
CollectorService._process_collector()
  -> MediaCrawlerPlatformCollector.fetch()
  -> resolve_effective_keywords()
  -> MediaCrawlerRunner.run(keywords)
  -> MediaCrawler command / fixture
```

Relevant locations:

- `backend/app/collectors/service.py`
  - selects the MediaCrawler round-robin keyword and passes
    `global_keywords`, `keyword_override`, `region_kw`, and `topic_kw`.
- `backend/app/collectors/media_crawler_platform_collector.py`
  - `fetch()` chooses `keyword_override` or calls
    `resolve_effective_keywords()`.
- `backend/app/collectors/mediacrawler_normalizers.py`
  - `resolve_effective_keywords()` currently resolves datasource-local
    `config_json.keywords`, then runtime keywords, then global keywords.
- `backend/app/collectors/mediacrawler_runner.py`
  - `run()` writes the selected keyword list into the crawler config and
    environment, then invokes the platform runner.

Before this change, `keyword_scope` was only accepted by the MediaCrawler
configuration validator. It did not participate in the search keyword list.

### 3. Last pre-Opinion entry point

The MediaCrawler JSONL path is:

```text
MediaCrawlerRunner output JSONL
  -> MediaCrawlerPlatformCollector._read_jsonl()
  -> _normalize_row()
  -> normalizer.normalize(row)
  -> dedup_key()
  -> returned normalized item list
  -> CollectorService._process_collector()
  -> Opinion creation
```

Relevant locations:

- `backend/app/collectors/media_crawler_platform_collector.py`
  - `_read_jsonl()` parses, normalizes, de-duplicates, and returns items.
  - `_normalize_row()` delegates to the registered platform normalizer.
- `backend/app/collectors/mediacrawler_normalizers.py`
  - `WeiboNormalizer` and `XhsNormalizer` map platform rows to the common
    collector item contract.
- `backend/app/collectors/service.py`
  - iterates over returned items and creates `Opinion`.

Before this change, `_read_jsonl()` only rejected malformed or empty rows.
It did not apply `filter_mode`, `apply_keyword_scope()`, or
`matches_region_topic()` before returning items.

### 4. Existing ordinary-collector implementation

The shared configuration helper is:

- `backend/app/collectors/source_config.py`
  - `DataSourceConfig.filter_mode(default)`
  - `DataSourceConfig.keyword_scope(default)`
  - `apply_keyword_scope(scope, region_kw, topic_kw)`

`apply_keyword_scope()` accepts two categorized lists and returns the
possibly reduced `(region_kw, topic_kw)` pair:

```python
region_kw, topic_kw = apply_keyword_scope(
    cfg.keyword_scope(),
    region_kw,
    topic_kw,
)
```

Ordinary collectors then pass the filtered lists and the configured matching
mode into the existing matcher. Representative implementations:

- `backend/app/collectors/xinhua_collector.py`
- `backend/app/collectors/people_collector.py`
- `backend/app/collectors/chinanews_collector.py`
- `backend/app/collectors/baidu_news_collector.py`
- `backend/app/collectors/generic_site.py`

Typical admission call:

```python
if not matches_region_topic(
    text,
    region_kw or [],
    topic_kw or [],
    match_mode=filter_mode,
):
    continue
```

The matcher is:

- `backend/app/collectors/common.py`
  - `matches_region_topic(text, region_kws, topic_kws, match_mode=...)`

Its supported modes are `region_only`, `region_or_topic`, and `topic_only`.
Its inputs are a text string plus the region/topic keyword lists produced by
the grouped keyword service and `apply_keyword_scope()`.

### 5. Configuration and compatibility observations

- `filter_mode` and `keyword_scope` are already present in
  `MEDIACRAWLER_CONFIG_KEYS`; no whitelist expansion is required.
- The existing helper vocabulary is `region`, `topic`, and `region_topic`.
  The implementation accepts `region_only` / `topic_only` as compatibility
  aliases and normalizes them back to the existing helper vocabulary, so the
  ordinary collector semantics remain unchanged.
- XHS has no platform-specific collector file in this workspace. The generic
  platform collector and registered XHS normalizer are the shared path for
  both Weibo and XHS.
- The existing `CollectorService` is the main Opinion writer and must remain
  unchanged under the requested architecture constraint. Therefore the
  MediaCrawler admission gate belongs in the shared collector after
  normalization and before items are returned to the service.
- Existing MediaCrawler runner metrics already support auditable counters.
  A MediaCrawler-specific skipped counter can be written to the run metrics
  without changing database tables or the service flow.

## Audit conclusion

The smallest consistent integration point is the shared
`MediaCrawlerPlatformCollector`:

1. resolve the existing effective keyword source;
2. apply `apply_keyword_scope()` to the categorized region/topic lists and
   reduce the search list only when `keyword_scope` is explicitly configured;
3. run the platform search;
4. normalize each raw row;
5. build one filter text from normalized title/content plus supported social
   metadata;
6. call `matches_region_topic()` with the configured `filter_mode`;
7. return only admitted items and record skipped rows in MediaCrawler metrics.

This keeps Weibo and XHS on one code path, preserves ordinary collectors, and
preserves the legacy MediaCrawler behavior when neither strategy key is
configured.
