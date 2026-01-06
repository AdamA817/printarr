# Channels

Channels are the primary source of 3D designs in Printarr. This guide covers adding, configuring, and managing channels.

## Adding a Channel

### From the UI

1. Navigate to **Channels** in the sidebar
2. Click **Add Channel**
3. Enter the channel identifier:
   - Username: `@FlexiFactorySTL` or `FlexiFactorySTL`
   - Invite link: `https://t.me/+abc123xyz` (for private channels)
   - Numeric ID: `-1001234567890`
4. Click **Add**

### Channel Types

| Type | Access | Example |
|------|--------|---------|
| Public | Anyone can join | `@FlexiFactorySTL` |
| Private | Invite link required | `https://t.me/+abc123` |

**Note:** For private channels, your Telegram account must already be a member.

## Channel Settings

### Download Modes

Each channel can have a different download mode:

| Mode | Behavior |
|------|----------|
| **Manual** | Only download designs you explicitly request |
| **Auto (New)** | Automatically download new posts after enabling |
| **Auto (All)** | Download everything, including backfilled history |

### Changing Settings

1. Go to **Channels**
2. Click on a channel
3. Use the **Settings** tab to adjust:
   - Download mode
   - Enable/disable monitoring
   - Custom library path override

## Backfill

Backfill retrieves historical messages from a channel.

### Starting a Backfill

1. Open a channel's detail page
2. Click **Backfill** in the header
3. Choose options:
   - **Full**: All messages ever posted
   - **Recent**: Last 30 days
   - **Custom**: Specify date range
4. Click **Start Backfill**

### Backfill Modes

| Mode | Description | Use Case |
|------|-------------|----------|
| **Metadata Only** | Catalog designs without downloading | Browse first, download later |
| **With Downloads** | Catalog and download files | Full archive |

### Monitoring Backfill Progress

- Progress bar on channel card
- Activity page shows backfill jobs
- Status in channel detail header

## Live Monitoring

When `PRINTARR_SYNC_ENABLED=true`, Printarr continuously monitors enabled channels.

### How It Works

1. Maintains connection to Telegram
2. Receives new messages in real-time
3. Processes posts containing 3D files
4. Queues downloads based on channel mode

### Catch-Up Sync

If Printarr restarts or loses connection:
1. Checks for missed messages since last sync
2. Processes them in batches
3. Returns to live monitoring

Configure with:
- `PRINTARR_SYNC_POLL_INTERVAL`: How often to check (seconds)
- `PRINTARR_SYNC_BATCH_SIZE`: Messages per batch

## Channel Discovery

Printarr can discover new channels from:

### Forwarded Messages

When a post is forwarded from another channel:
1. Printarr detects the source channel
2. Shows in **Discover** tab
3. One-click to add the channel

### Mentioned Channels

Links like `@AnotherChannel` in posts are detected and shown as suggestions.

### Viewing Suggestions

1. Go to **Channels**
2. Click **Discover** tab
3. Review suggested channels
4. Click **Add** or **Dismiss**

## Managing Channels

### Enabling/Disabling

- **Enabled**: Channel is actively monitored
- **Disabled**: No new syncing, existing designs remain

Toggle via the switch on channel cards or detail page.

### Removing a Channel

1. Open channel detail
2. Click **Settings** tab
3. Click **Remove Channel**
4. Choose whether to keep or delete designs

**Note:** Removing a channel doesn't delete downloaded files from your library.

## Channel Statistics

Each channel shows:

| Stat | Description |
|------|-------------|
| **Designs** | Total designs cataloged |
| **Downloaded** | Designs with files downloaded |
| **Wanted** | Marked for download but not yet processed |
| **Last Sync** | When channel was last checked |

## Troubleshooting

### "Channel Not Found"

- Verify the username/link is correct
- Ensure your account has access (for private channels)
- Try the numeric channel ID

### "Access Denied"

- You must be a member of private channels
- Join the channel in Telegram first, then add in Printarr

### Backfill Stuck

- Check logs for rate limit errors
- Lower rate limit settings
- Try a smaller batch size

### Missing Recent Posts

- Ensure channel is enabled
- Check sync status in Settings > Telegram
- Verify no flood wait is active
