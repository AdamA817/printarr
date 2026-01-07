# Settings Reference

Complete guide to all settings available in the Printarr UI.

## Accessing Settings

Click **Settings** in the sidebar to access configuration options.

## Telegram Settings

### Connection Status

Shows current Telegram connection state:
- **Connected**: Active session, ready to sync
- **Disconnected**: No active connection
- **Authenticating**: Login in progress

### Authentication

If not connected:
1. Click **Connect**
2. Enter phone number
3. Enter verification code from Telegram
4. Enter 2FA password if enabled

### Rate Limiting

| Setting | Description |
|---------|-------------|
| **Requests per minute** | Max API calls/minute (10-100) |
| **Channel spacing** | Seconds between same-channel requests |

Lower these values if you see FloodWait errors.

### Sync Settings

| Setting | Description |
|---------|-------------|
| **Enable live monitoring** | Continuously watch for new posts |
| **Poll interval** | Catch-up check frequency (seconds) |
| **Batch size** | Messages per sync batch |

## Download Settings

### Concurrency

**Max concurrent downloads**: How many downloads run in parallel (1-10)

Higher values = faster but more resource usage.

### Library Template

Define how files are organized:

```
{designer}/{title}
```

See [Downloads](downloads.md) for all template variables.

### Archive Handling

| Setting | Description |
|---------|-------------|
| **Auto-extract** | Extract archives after download |
| **Delete archives** | Remove archive after extraction |
| **Recursive extraction** | Extract nested archives |

## Google Drive Settings

### Connection

Click **Connect** to start OAuth flow:
1. Opens Google login
2. Grant Printarr access
3. Redirect back to Printarr

### Rate Limits

| Setting | Description |
|---------|-------------|
| **Request delay** | Seconds between API calls |
| **Requests per minute** | Max API calls/minute |

## Render Settings

### Auto-Render

| Setting | Description |
|---------|-------------|
| **Auto-queue renders** | Generate previews after import |
| **Render priority** | Queue priority for auto-renders |

### Render Quality

| Setting | Description |
|---------|-------------|
| **Thumbnail size** | Preview image dimensions |
| **Render angles** | Number of preview angles |

## Thangs Integration

### FlareSolverr

Enter your FlareSolverr URL to enable Thangs integration:

```
http://flaresolverr:8191/v1
```

### Auto-Linking

| Setting | Description |
|---------|-------------|
| **Auto-search** | Search Thangs for new designs |
| **Auto-link threshold** | Confidence required for auto-linking |

## AI Analysis Settings

AI-powered tagging uses Google Gemini to automatically categorize and tag designs.

### Getting Started

1. Get a free API key from [Google AI Studio](https://aistudio.google.com/app/apikey)
2. Enable AI analysis in Settings
3. Enter your API key
4. New imports will be automatically analyzed

### Settings

| Setting | Description |
|---------|-------------|
| **Enable AI analysis** | Turn on/off AI tagging |
| **API key** | Google Gemini API key |
| **Model** | AI model to use (default: gemini-1.5-flash) |
| **Auto-analyze on import** | Analyze new designs automatically |
| **Select best preview** | Let AI choose the best preview image |
| **Rate limit (RPM)** | Max requests per minute (5-60) |
| **Max tags per design** | Limit on AI-generated tags (1-30) |

### Model Options

| Model | Speed | Quality | Cost |
|-------|-------|---------|------|
| gemini-1.5-flash | Fast | Good | Lowest |
| gemini-1.5-pro | Medium | Better | Higher |
| gemini-2.0-flash | Fastest | Good | Low |

### Free Tier Limits

Google AI's free tier includes:
- 15 requests per minute
- 1 million tokens per day
- 1,500 requests per day

This is sufficient for most personal libraries. The default rate limit (15 RPM) stays within free tier bounds.

### Manual Analysis

To analyze existing designs:
1. Select designs in the grid
2. Click **Bulk Actions** > **Analyze with AI**
3. Analysis runs in background

Or for individual designs:
1. Open design detail page
2. Click **Analyze** button

## Upload Settings

| Setting | Description |
|---------|-------------|
| **Max file size** | Maximum upload size (MB) |
| **Retention period** | Hours to keep unprocessed uploads |

## System Settings

### Logging

| Setting | Description |
|---------|-------------|
| **Log level** | Verbosity: DEBUG, INFO, WARNING, ERROR |
| **Debug mode** | Enable detailed debugging |

### Database

| Setting | Description |
|---------|-------------|
| **Vacuum database** | Optimize database file |
| **Export data** | Download database backup |

### Maintenance

| Action | Description |
|--------|-------------|
| **Clear cache** | Delete all cached thumbnails |
| **Reset statistics** | Clear activity history |
| **Factory reset** | Delete all data (dangerous!) |

## Setting Persistence

Settings are stored in two places:

1. **Environment variables**: Initial defaults, read at startup
2. **Database**: UI changes, override environment defaults

To reset a setting to its environment default:
1. Delete the setting row in the database
2. Or use "Reset to Default" in the UI

## Recommended Configurations

### Home Server

```yaml
PRINTARR_MAX_CONCURRENT_DOWNLOADS: 2
PRINTARR_TELEGRAM_RATE_LIMIT_RPM: 30
PRINTARR_SYNC_POLL_INTERVAL: 300
```

### High-Volume

```yaml
PRINTARR_MAX_CONCURRENT_DOWNLOADS: 5
PRINTARR_TELEGRAM_RATE_LIMIT_RPM: 20  # Lower to avoid limits
PRINTARR_SYNC_BATCH_SIZE: 50
```

### Low-Resource

```yaml
PRINTARR_MAX_CONCURRENT_DOWNLOADS: 1
PRINTARR_AUTO_QUEUE_RENDER_AFTER_IMPORT: false  # Save CPU
PRINTARR_SYNC_POLL_INTERVAL: 600
```

### With AI Tagging

```yaml
PRINTARR_AI_ENABLED: true
PRINTARR_AI_API_KEY: your_api_key_here
PRINTARR_AI_MODEL: gemini-1.5-flash  # Best cost/quality balance
PRINTARR_AI_RATE_LIMIT_RPM: 15  # Free tier safe
PRINTARR_AI_AUTO_ANALYZE_ON_IMPORT: true
```
