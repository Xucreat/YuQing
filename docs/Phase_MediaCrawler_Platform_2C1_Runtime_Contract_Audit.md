# Phase MediaCrawler Platform-2-C1

## Status

`BLOCKED`

The XHS runtime contract was found and is auditable. The current application
adapter is not yet compatible with the discovered profile contract, and the
current `PlatformSpec.crawler_type` field cannot represent XHS's three native
crawler modes. No implementation was performed in this discovery phase.

## Contract Source

`FOUND`

The configured external checkout was inspected read-only:

- Location: `D:\code files\mediaCrawler\MediaCrawler`
- Branch: `main`
- Commit: `1779dde9725f6b7ef42e29022c0054b3e678f1af`
- Project version: `0.1.0` (`pyproject.toml`)
- Python requirement: `>=3.11`
- CLI entry: `main.py`
- CLI parser: `cmd_arg/arg.py`

The checkout itself has unrelated dirty files and runtime artifacts. The
contract below is based on the inspected source files and the pinned `HEAD`;
no external checkout files were changed.

## Source Evidence

The relevant source locations are:

- `cmd_arg/arg.py`: `PlatformEnum.XHS = "xhs"`, login and crawler enums, and
  `--platform`, `--lt`, `--type`, `--save_data_option`, and
  `--save_data_path` options.
- `main.py`: `CrawlerFactory.CRAWLERS["xhs"] = XiaoHongShuCrawler`.
- `media_platform/xhs/core.py`: XHS lifecycle, login selection, search/detail/
  creator dispatch, and browser profile construction.
- `media_platform/xhs/login.py`: qrcode, phone, and cookie login branches.
- `store/xhs/__init__.py`: note-to-storage field transformation.
- `store/xhs/_store_impl.py`: JSONL store selection for XHS content/comments.
- `tools/async_file_writer.py`: platform/item-type/date JSONL path contract.
- `config/base_config.py` and `config/xhs_config.py`: XHS defaults and
  platform-specific input lists.

## CLI Contract

Confirmed native values:

| Contract | Confirmed value |
|---|---|
| platform | `xhs` |
| crawler_type | `search`, `detail`, `creator` |
| login | `qrcode`, `phone`, `cookie` |
| output option | `jsonl` |
| output path option | `--save_data_path <directory>` |
| keyword option | `--keywords <comma-separated>` |
| comments | `--get_comment`, `--get_sub_comment` |
| item limit | `--crawler_max_notes_count` |

The application-level platform label may remain `xiaohongshu`, but the native
CLI code must be `xhs`. No `wb`, `weibo`, or `weibo.jsonl` value is part of the
XHS contract.

The current application command builder intentionally rejects the unresolved
XHS skeleton (`cli_code=UNKNOWN`, `crawler_type=UNKNOWN`, and no supported
login types). That fail-closed behavior is correct for the current phase.

## JSONL Contract

The native XHS JSONL writer creates separate files under:

```text
<save_data_path>/xhs/jsonl/<crawler_type>_contents_<date>.jsonl
<save_data_path>/xhs/jsonl/<crawler_type>_comments_<date>.jsonl
```

The content JSONL item is the storage-transformed note, not the raw API
response. Confirmed content fields and source shape are:

| Field | Source/type observation |
|---|---|
| `note_id` | XHS note id, string |
| `type` | `normal` or `video`, string |
| `title` | string; falls back to a description prefix |
| `desc` | note body, string |
| `video_url` | derived string, possibly empty |
| `time` | publish time, normally epoch milliseconds |
| `last_update_time` | integer timestamp |
| `creator_hash` | derived user identifier hash; may be absent/null |
| `nickname` | masked author nickname; may be absent/null |
| `liked_count` | interaction count, source-preserved scalar |
| `collected_count` | interaction count, source-preserved scalar |
| `comment_count` | interaction count, source-preserved scalar |
| `share_count` | interaction count, source-preserved scalar |
| `image_list` | joined image URL string |
| `tag_list` | joined topic-name string |
| `last_modify_ts` | generated timestamp |
| `note_url` | constructed XHS URL string |
| `source_keyword` | current keyword context, string |
| `xsec_token` | source token field; sensitive and must not enter fixtures/logs |

The internal note object uses nested `user`, `interact_info`, `image_list`,
`tag_list`, and `video` structures before storage transformation. The final
JSONL contract therefore requires a sanitized fixture from the exact checkout
before production enablement. No real XHS output was used in this audit.

Comment JSONL is a separate output stream and includes at least the comment
identifier, note id, content, create time, masked author, and sub-comment
count. Comment normalization is outside the current application opinion
contract and must be handled explicitly in a later phase.

## Current MediaCrawler Architecture

The current application call chain is:

```text
registry.resolve_collectors_verbose
  -> source_config.validate_data_source_config
  -> get_mediacrawler_platform_spec
  -> import_class
  -> MediaCrawlerPlatformCollector.fetch
  -> MediaCrawlerRuntimeFactory / MediaCrawlerRunner
  -> MediaCrawlerCommandBuilder
  -> native JSONL discovery and raw artifact preservation
  -> get_mediacrawler_normalizer
  -> CollectorService admission and writeback
```

Relevant application files and functions:

- `backend/app/collectors/registry.py`: source discovery and capability-based
  MediaCrawler assembly.
- `backend/app/collectors/media_crawler_platform_collector.py`:
  platform-neutral fetch, JSONL parsing, deduplication, error isolation, and
  runtime profile cleanup.
- `backend/app/collectors/mediacrawler_platform.py`: `PlatformSpec` and
  registry, including `WEIBO_PLATFORM_SPEC` and the unresolved XHS skeleton.
- `backend/app/collectors/mediacrawler_normalizers.py`: normalizer registry,
  Weibo normalizer, XHS offline normalizer, date/count helpers.
- `backend/app/collectors/mediacrawler_command_builder.py`: shell-free argv
  construction and unresolved-contract rejection.
- `backend/app/collectors/mediacrawler_runner.py`: fixture/mock/real-run gate,
  native JSONL discovery, raw preservation, bounded output, and metrics.
- `backend/app/collectors/mediacrawler_batch.py`: batch raw/output/metrics
  paths derived from the platform spec.
- `backend/app/collectors/mediacrawler_runtime.py`: trigger, platform, source
  key, profile, lock, and scheduler runtime assembly.
- `backend/app/collectors/mediacrawler_weibo_compatibility.py` and
  `media_crawler_weibo_collector.py`: Weibo-only legacy compatibility.

## Runtime Compatibility

### Profile

`NOT_COMPATIBLE_YET`.

The application currently resolves isolated profiles as:

```text
<profile_root>/<platform>/<data_source_key>/<manual|scheduler>
```

The runtime injects `MEDIA_CRAWLER_PROFILE_NAME` and
`MEDIA_CRAWLER_BROWSER_DATA`, but the inspected upstream XHS code does not
read either variable. `media_platform/xhs/core.py` instead constructs:

```text
<cwd>/browser_data/<config.USER_DATA_DIR % config.PLATFORM>
```

which resolves to `browser_data/xhs_user_data_dir` for XHS. Therefore the
current application profile isolation is not proven to reach the XHS browser
context. This is the primary blocker for a real runtime contract.

### Artifact

`COMPATIBLE_AFTER_SPEC_RESOLUTION`.

The application can preserve an internal artifact named `xiaohongshu.jsonl`
while discovering the native output under `xhs/jsonl`. The discovered native
output parts must therefore be `("xhs", "jsonl")`; they must not be inferred
from the internal artifact name.

### Batch and raw output

`COMPATIBLE` at the application boundary. `MediaCrawlerBatchLocator` and
`MediaCrawlerRunner` derive raw/output paths from `PlatformSpec.artifact_name`
and isolate them by batch and artifact scope. The native locator can consume
the XHS `xhs/jsonl` subdirectory after the spec is resolved.

### Lock

`COMPATIBLE` at the generic application boundary. Runtime locks are scoped by
platform and source key for non-legacy platforms. Weibo's empty-scope legacy
policy remains isolated in `WeiboCompatibilityPolicy` and is not reused for
XHS.

### Real-run gate

`CLOSED`. The application settings keep both real-run controls disabled in
the inspected environment, and this audit did not invoke the runner, CLI,
Scheduler, or any browser.

## Required Changes

`LIST` - required before XHS runtime enablement, but not implemented in
Platform-2-C1:

1. Resolve the XHS `PlatformSpec` with `cli_code="xhs"`, native output parts
   `("xhs", "jsonl")`, supported login types `{qrcode, phone, cookie}`, and
   an explicit representation of the allowed crawler types
   `{search, detail, creator}`. The current single-value `crawler_type` field
   needs a generic contract extension or an equivalent generic mode contract.
2. Add a reviewed runtime/profile adapter contract that the upstream entry
   actually consumes. It must preserve `trigger/platform/data_source_key`
   isolation without putting a shell command, credentials, or profile path in
   `config_json`. An external wrapper or upstream-supported profile setting
   must be proven with an offline fake-run test before any real gate changes.
3. Add sanitized XHS native-output fixtures and command/artifact/profile
   contract tests. Fixtures must exclude cookies, tokens, and browser state;
   the source field `xsec_token` must be redacted or omitted from retained
   application artifacts according to an explicit policy.
4. Keep `allow_real_collection=False` until the above tests and an operator
   review establish the runtime contract. No DataSource, model, migration,
   Scheduler, or CollectorService business change is implied by this audit.

## Database Impact

`NONE`.

The existing `DataSource.config_json` platform contract and generic collector
registry are sufficient to carry a future XHS source key. No new model field,
table, schema change, or migration is required by the discovered contract.

## Scheduler Impact

`NONE` for this phase.

The Scheduler must not be changed. Once a generic runtime/profile adapter is
proven, the existing trigger and lock contract can be reused. Scheduler login
must remain non-interactive and must use a validated persistent profile.

## Test Plan

Before 2-C2 can be marked ready, add or run offline-only tests for:

1. Exact `XHS_PLATFORM_SPEC` values and allowed crawler modes.
2. Command argv snapshots for `xhs`, all supported crawler modes, each
   supported login type, `jsonl`, and `save_data_path`.
3. Assertions that XHS argv and native paths contain no Weibo values.
4. Native output discovery from `xhs/jsonl` into the internal artifact path.
5. Profile propagation through the approved adapter using a fake runner,
   including manual/scheduler and source-key isolation.
6. Lock, batch, raw, output, and metrics isolation.
7. Sanitized content/comment JSONL fixtures, missing fields, epoch timestamps,
   engagement values, malformed lines, and duplicate records.
8. Closed real-run gate proving no subprocess starts.
9. Existing Weibo fixture, class path, legacy artifact path, and production
   observation regression tests.

The existing XHS B1/B2 tests were read as part of this audit. They correctly
test the unresolved skeleton and offline pipeline, but they do not prove the
newly discovered upstream XHS runtime or profile contract. No test suite was
executed in this discovery-only phase.

## Risk

Overall: `HIGH` for real enablement, `LOW` for current production impact.

| Risk area | Level | Assessment |
|---|---|---|
| Architecture | HIGH | Profile propagation is not consumed upstream; crawler type is multi-valued while the current spec field is scalar. |
| Data structure | MEDIUM | Final JSONL is a storage-transformed shape with optional fields and a sensitive token field. |
| Login | HIGH | QR-code and phone flows are interactive; cookie login depends on a validated persistent browser profile. |
| Collection stability | HIGH | Browser/session behavior, XHS anti-bot checks, and output naming require exact-version validation. |
| Production impact | LOW currently | Real-run controls are closed and no XHS production DataSource or Scheduler was enabled. |

## Recommendation

`BLOCKED`

Do not proceed to XHS runtime enablement until the profile propagation issue
and multi-mode crawler contract are resolved generically and covered by
offline tests. The external source evidence is sufficient to begin the next
adapter-design task, but not sufficient to claim `READY_FOR_2C2` for an
executable XHS path.

## Explicit Phase Confirmation

- No real XHS collection was executed.
- No real MediaCrawler process was started.
- No Scheduler was started or modified.
- No production DataSource was modified.
- No database, model, migration, or `.env` was modified.
- No real account, Cookie, token, or browser profile was used.
- No application code or tests were modified in Platform-2-C1.

State: `CONTRACT_DISCOVERY_ONLY`
