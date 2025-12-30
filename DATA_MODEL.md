# DATA_MODEL

This document describes the logical data model required to support:
- Telegram ingestion (channels, messages, attachments)
- A deduplicated “Design” catalog with multiple sources
- Download/import workflow state
- Tags, previews, and derived artifacts

The model below is written to fit either SQLite or Postgres.

---

## 1. Entities

### 1.1 Channel
Represents a monitored Telegram channel/group.

Key fields:
- `id` (uuid/int)
- `telegram_peer_id` (string/int; unique)
- `title`
- `username` (optional; `t.me/<username>`)
- `invite_link` (optional)
- `is_private` (bool)
- `is_enabled` (bool)

Channel settings:
- `backfill_mode` (enum: ALL_HISTORY | LAST_N_MESSAGES | LAST_N_DAYS)
- `backfill_value` (int; N messages or N days)
- `download_mode` (enum: DOWNLOAD_ALL | DOWNLOAD_ALL_NEW | MANUAL)
- `library_template_override` (optional string template)
- `title_source_override` (optional enum)
- `designer_source_override` (optional enum)

Sync state:
- `last_ingested_message_id` (optional)
- `last_backfill_checkpoint` (optional)
- `last_sync_at` (timestamp)

Indexes:
- unique(`telegram_peer_id`)
- index(`is_enabled`, `last_sync_at`)

---

### 1.2 TelegramMessage
Raw message metadata (useful for audit + reprocessing).

Fields:
- `id`
- `channel_id`
- `telegram_message_id` (unique within channel)
- `date_posted` (timestamp)
- `author_name` (optional; may not exist for channels)
- `caption_text` (optional)
- `caption_text_normalized` (optional)
- `has_media` (bool)

Indexes:
- unique(`channel_id`, `telegram_message_id`)
- index(`channel_id`, `date_posted`)

---

### 1.3 Attachment
A file or media item attached to a Telegram message.

Fields:
- `id`
- `message_id`
- `telegram_file_id` (optional; unique if available)
- `telegram_unique_file_id` (optional)
- `media_type` (enum: DOCUMENT | PHOTO | VIDEO | OTHER)
- `filename` (optional)
- `mime_type` (optional)
- `size_bytes` (optional)
- `ext` (optional; derived)
- `is_candidate_design_file` (bool)
- `download_status` (enum: NOT_DOWNLOADED | DOWNLOADING | DOWNLOADED | FAILED)
- `download_path` (optional; staging path)
- `sha256` (optional; computed post-download)

Indexes:
- index(`message_id`)
- index(`is_candidate_design_file`)
- index(`sha256`)

---

### 1.4 Design
A deduplicated catalog item that may have multiple sources.

Fields:
- `id`
- `canonical_title` (string)
- `canonical_designer` (string; default "Unknown")
- `multicolor` (enum: UNKNOWN | SINGLE | MULTI)
- `status` (enum: DISCOVERED | WANTED | DOWNLOADING | DOWNLOADED | ORGANIZED)
- `primary_file_types` (set/array or derived view)
- `total_size_bytes` (optional; sum of best source)
- `created_at` (timestamp)
- `updated_at` (timestamp)

User overrides:
- `title_override` (optional)
- `designer_override` (optional)
- `multicolor_override` (optional enum)

Indexes:
- index(`status`)
- index(`canonical_designer`)
- index(`multicolor`)
- index(`created_at`)

---

### 1.5 DesignSource
Links a Design to one Telegram message (source), with per-source data.

Fields:
- `id`
- `design_id`
- `channel_id`
- `message_id`
- `source_rank` (int; heuristic score)
- `is_preferred` (bool)
- `caption_snapshot` (optional)

Indexes:
- unique(`channel_id`, `message_id`)  (one source record per message)
- index(`design_id`)

---

### 1.6 DesignFile
Represents a file that belongs to a design (from a source attachment and/or extracted archive).

Fields:
- `id`
- `design_id`
- `source_attachment_id` (nullable; may be from extraction)
- `relative_path` (string; within design folder)
- `filename` (string)
- `ext` (string)
- `size_bytes` (optional)
- `sha256` (optional)
- `file_kind` (enum: MODEL | ARCHIVE | IMAGE | OTHER)
- `model_kind` (enum: STL | THREE_MF | OBJ | STEP | UNKNOWN)
- `is_from_archive` (bool)
- `archive_parent_id` (nullable to another DesignFile)
- `is_primary` (bool)

Indexes:
- index(`design_id`)
- index(`sha256`)
- index(`ext`, `file_kind`)

---

### 1.7 Tag
- `id`
- `name` (unique)
- `created_at`

### 1.8 DesignTag (join)
- `design_id`
- `tag_id`
- `source` (enum: AUTO | MANUAL)
- unique(`design_id`, `tag_id`)

Indexes:
- index(`tag_id`)
- index(`design_id`)

---

### 1.9 PreviewAsset
Stores references to preview images.

Fields:
- `id`
- `design_id`
- `kind` (enum: TELEGRAM_IMAGE | THREE_MF_EMBEDDED | RENDERED)
- `source_attachment_id` (nullable)
- `path` (string; in `/cache` or `/library`)
- `width` (optional)
- `height` (optional)
- `created_at`

Constraints:
- limit TELEGRAM_IMAGE count to 10 per design (enforced at ingest or UI)

Indexes:
- index(`design_id`, `kind`)

---

### 1.10 Job
Tracks background work and feeds the Activity UI.

Fields:
- `id`
- `type` (enum; see below)
- `status` (QUEUED | RUNNING | SUCCESS | FAILED | CANCELED)
- `priority` (int)
- `channel_id` (nullable)
- `design_id` (nullable)
- `payload_json` (json)
- `progress_current` (optional)
- `progress_total` (optional)
- `attempts` (int)
- `max_attempts` (int)
- `last_error` (optional text)
- `created_at`, `started_at`, `finished_at`

Job types (minimum):
- BACKFILL_CHANNEL
- SYNC_CHANNEL_LIVE
- DOWNLOAD_DESIGN
- EXTRACT_ARCHIVE
- ANALYZE_3MF
- GENERATE_RENDER
- IMPORT_TO_LIBRARY
- DEDUPE_RECONCILE

Indexes:
- index(`status`, `type`, `priority`)
- index(`design_id`)
- index(`channel_id`)

---

## 2. Derived / Search Views (Recommended)

To support fast faceted search, create a materialized or computed view:

### 2.1 DesignSearchView
- `design_id`
- `status`
- `designer`
- `title`
- `multicolor`
- `file_types` (string/array)
- `channels` (string/array)
- `tags` (string/array)
- `has_previews` (bool)
- `created_at`

Indexes depend on DB, but prioritize:
- status
- designer
- multicolor
- created_at
- tags (FTS or join index)
- title (FTS recommended)

---

## 3. Dedupe Strategy Hooks

To support evolving heuristics, store a table:

### 3.1 DedupeEvidence
- `id`
- `design_id_a`
- `design_id_b`
- `evidence_type` (HASH_MATCH | FILENAME_SIZE_MATCH | CAPTION_SIMILARITY | MANUAL_MERGE)
- `score` (float)
- `created_at`

Allows later reconciliation jobs to merge designs.

---

## 4. External Metadata Entities

### 4.1 ExternalMetadataSource
Links a Design to an external metadata authority (Thangs, Printables, etc.).

Fields:
- `id`
- `design_id`
- `source_type` (enum: THANGS | PRINTABLES | THINGIVERSE)
- `external_id` (string; model ID on external platform)
- `external_url` (string; canonical URL)
- `confidence_score` (float; 0.0-1.0)
- `match_method` (enum: LINK | TEXT | GEOMETRY | MANUAL)
- `is_user_confirmed` (bool)
- `fetched_title` (string; title from external source)
- `fetched_designer` (string; designer from external source)
- `fetched_tags` (array/json; tags from external source)
- `last_fetched_at` (timestamp)
- `created_at`

Indexes:
- unique(`design_id`, `source_type`)
- index(`source_type`)
- index(`external_id`)

---

### 4.2 ExternalImage
Preview images from external metadata sources.

Fields:
- `id`
- `external_source_id`
- `image_url` (string; remote URL)
- `local_cache_path` (string; cached path in /cache)
- `sort_order` (int)
- `width` (optional)
- `height` (optional)
- `created_at`

Indexes:
- index(`external_source_id`)

---

### 4.3 Design Extensions for Metadata Authority
Additional fields on Design entity:

- `metadata_authority` (enum: TELEGRAM | THANGS | PRINTABLES | USER; indicates current source of truth)
- `metadata_confidence` (float; confidence in current metadata)

Precedence logic:
1. User overrides (title_override, designer_override) always win
2. If ExternalMetadataSource exists with is_user_confirmed=true, use fetched values
3. If ExternalMetadataSource exists with high confidence, use fetched values
4. Fall back to Telegram heuristics

---

## 5. Notes

- Keep Telegram raw entities (messages, attachments) so you can re-run extraction rules without losing history.
- Prefer computing hashes after download; store them in Attachment/DesignFile.
- Allow overrides at the Design level; never overwrite user overrides with auto-parsed data.
- External metadata is additive; it enriches but never destroys Telegram-sourced data.
- External images are cached locally to avoid repeated fetches and for offline viewing.
