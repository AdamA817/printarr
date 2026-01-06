# Import Sources

Printarr supports multiple ways to import 3D designs beyond Telegram channels.

## Google Drive Integration

Import designs directly from Google Drive folders.

### Setup

See [Google Drive Setup](GOOGLE_DRIVE_SETUP.md) for detailed OAuth configuration.

Quick overview:
1. Create OAuth credentials in Google Cloud Console
2. Configure `PRINTARR_GOOGLE_CLIENT_ID` and `PRINTARR_GOOGLE_CLIENT_SECRET`
3. Authenticate in Settings > Import Sources > Google Drive

### Adding a Drive Source

1. Go to **Import Sources**
2. Click **Add Google Drive**
3. Paste a Google Drive folder URL
4. Configure options:
   - **Name**: Display name for this source
   - **Auto-import**: Automatically import new files
   - **Schedule**: How often to check for new files
5. Click **Add**

### Supported URLs

- Folder: `https://drive.google.com/drive/folders/abc123`
- Shared folder: `https://drive.google.com/drive/folders/abc123?usp=sharing`

### Import Options

| Option | Description |
|--------|-------------|
| **Manual** | Only import when you click Import |
| **Auto (New)** | Import new files automatically |
| **Watch** | Continuously monitor for changes |

### File Handling

Google Drive imports:
1. List files in folder (recursive optional)
2. Filter for 3D file types
3. Download to staging
4. Create design entries
5. Move to library

### Rate Limits

Google Drive API has quotas:
- `PRINTARR_GOOGLE_REQUESTS_PER_MINUTE`: Default 60
- `PRINTARR_GOOGLE_REQUEST_DELAY`: Delay between requests

## File Uploads

Upload files directly through the web UI.

### Uploading

1. Go to **Import Sources**
2. Click **Upload Files**
3. Drag and drop or browse for files
4. Configure:
   - Design title
   - Designer (optional)
   - Tags (optional)
5. Click **Upload**

### Supported Uploads

- Individual files: STL, 3MF, OBJ, STEP
- Archives: ZIP, RAR, 7z, TAR
- Maximum size: `PRINTARR_UPLOAD_MAX_SIZE_MB` (default 500MB)

### Upload Retention

Unprocessed uploads are cleaned up after `PRINTARR_UPLOAD_RETENTION_HOURS` (default 24 hours).

## Bulk Folder Import

Monitor local folders for new 3D files.

### Setup

Mount folders as `/watch/*` volumes:

```yaml
volumes:
  - /path/to/downloads:/watch/downloads:ro
  - /path/to/patreon:/watch/patreon:ro
```

**Note:** Use `:ro` (read-only) for safety unless you want Printarr to move files.

### Adding a Watch Folder

1. Go to **Import Sources**
2. Click **Add Watch Folder**
3. Select from available mount points
4. Configure:
   - **Pattern**: File pattern (e.g., `*.stl`, `**/*.zip`)
   - **Mode**: Manual, Auto (New), or Watch
   - **Post-import**: Leave, Move, or Delete source files
5. Click **Add**

### Scan Modes

| Mode | Behavior |
|------|----------|
| **Manual** | Scan only when you click Scan |
| **Scheduled** | Scan at regular intervals |
| **Watch** | Monitor for filesystem changes |

### Import Profiles

Create profiles for different import behaviors:

1. Go to **Import Sources** > **Profiles**
2. Click **New Profile**
3. Configure:
   - Designer name template
   - Library path override
   - Auto-tagging rules
4. Assign profile when adding sources

### Duplicate Detection

When importing, Printarr checks for duplicates:
- File hash matching
- Thangs similarity (if enabled)
- Manual confirmation for uncertain matches

## Managing Sources

### Source Status

Each source shows:
- Last checked time
- Files found/imported
- Error status

### Refreshing

- **Refresh**: Check for new files now
- **Full Scan**: Re-scan entire source
- **Clear Cache**: Reset file tracking

### Removing Sources

1. Click source settings
2. Select **Remove**
3. Choose whether to keep imported designs

## Import Queue

Imports use the same queue as downloads:
- View in **Activity** page
- Same priority system
- Retry failed imports

## Troubleshooting

### Google Drive: "Access Denied"

- Re-authenticate OAuth connection
- Check folder sharing settings
- Verify folder ID is correct

### Watch Folder Not Detecting Files

- Verify volume mount is correct
- Check file permissions
- Ensure file matches pattern

### Duplicate Imports

- Enable duplicate detection
- Check if files have same hash
- Use import profiles for deduplication

### Large Folder Slow to Scan

- Use specific file patterns
- Enable scheduled scans instead of watch
- Increase Google rate limits (if Drive)
