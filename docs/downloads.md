# Downloads & Library

This guide covers the download queue, job management, and library organization.

## Download Queue

### Viewing the Queue

Navigate to **Activity** to see:
- **Queue**: Pending and running downloads
- **History**: Completed and failed jobs
- **Stats**: Queue metrics

### Job Priorities

Jobs are processed by priority (higher = sooner):

| Priority | Value | Use Case |
|----------|-------|----------|
| Urgent | 10 | Manual "Download Now" |
| High | 5 | User-initiated wants |
| Normal | 0 | Auto-downloads |
| Low | -5 | Background tasks |
| Background | -10 | Auto-renders |

### Job Statuses

| Status | Meaning |
|--------|---------|
| **Pending** | Waiting in queue |
| **Running** | Currently processing |
| **Completed** | Successfully finished |
| **Failed** | Error occurred (see details) |
| **Canceled** | Manually stopped |

## Managing Jobs

### Prioritize a Job

1. Find the job in the queue
2. Click the priority arrows or menu
3. Move up/down or set specific priority

### Cancel a Job

1. Click the job's menu (three dots)
2. Select **Cancel**
3. Confirm cancellation

### Retry a Failed Job

1. Go to **History**
2. Find the failed job
3. Click **Retry**

### Clear History

- **Clear Completed**: Remove successful jobs
- **Clear Failed**: Remove failed jobs
- **Clear All**: Reset history

## Download Process

### Telegram Downloads

1. Job enters queue
2. Worker claims the job
3. Connects to Telegram
4. Downloads file(s) to staging
5. Extracts archives if needed
6. Moves to library
7. Queues preview render (if enabled)

### Archive Handling

Printarr extracts these formats:
- ZIP
- RAR
- 7z
- TAR/TGZ/TAR.GZ

Nested archives are extracted recursively.

### Rate Limiting

Downloads respect Telegram's rate limits:
- Configurable requests per minute
- Automatic backoff on flood errors
- Per-channel spacing

## Library Organization

### Template System

Files are organized using the template in `PRINTARR_LIBRARY_TEMPLATE`.

Default: `{designer}/{title}`

### Available Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `{designer}` | Designer name | `FlexiFactory` |
| `{channel}` | Source channel | `FlexiFactorySTL` |
| `{title}` | Design title | `Flexi Dragon` |
| `{date}` | Post date | `2024-01-15` |
| `{year}` | Year | `2024` |
| `{month}` | Month | `01` |
| `{day}` | Day | `15` |

### Example Structures

```
# By designer (default)
{designer}/{title}
/library/FlexiFactory/Flexi Dragon/

# By channel and date
{channel}/{year}/{month}/{title}
/library/FlexiFactorySTL/2024/01/Flexi Dragon/

# Flat by date
{year}-{month}-{day}_{designer}_{title}
/library/2024-01-15_FlexiFactory_Flexi Dragon/
```

### File Naming

Within each design folder:
- Original file names are preserved
- Duplicates get numbered suffixes
- Special characters are sanitized

## Staging Area

The `/staging` volume is used for:
- Active downloads in progress
- Archive extraction
- File processing

### Cleanup

Staging is automatically cleaned:
- Successful jobs: Files moved to library
- Failed jobs: Files removed after retention period
- Orphaned files: Periodic cleanup

### Space Requirements

Recommend 2-5x your largest expected download:
- Large archives need room to extract
- Multiple concurrent downloads

## Concurrent Downloads

Control parallelism with `PRINTARR_MAX_CONCURRENT_DOWNLOADS`:

| Value | Use Case |
|-------|----------|
| 1 | Slow connection, minimal resources |
| 2-3 | Default, balanced |
| 5+ | Fast connection, beefy server |

Higher values = faster throughput but more:
- Network bandwidth usage
- Disk I/O
- Risk of rate limiting

## Troubleshooting

### Download Stuck at 0%

- Check Telegram connection (Settings > Telegram)
- Verify rate limits aren't exceeded
- Check container logs for errors

### "File Not Found" Error

- The original message may have been deleted
- The file may have expired
- Try re-syncing the channel

### Archive Extraction Failed

- File may be corrupted
- Password-protected archives not supported
- Check disk space in staging

### Files in Wrong Location

- Verify your library template
- Check designer/title on the design
- Template changes don't move existing files

### Slow Downloads

- Telegram limits download speeds
- Lower concurrent downloads to reduce contention
- Check your network connection
