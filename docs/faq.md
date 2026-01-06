# Frequently Asked Questions

## General

### What is Printarr?

Printarr is a self-hosted application that monitors Telegram channels for 3D-printable designs, catalogs them, and organizes downloads into a structured library. It's inspired by tools like Radarr and Sonarr but designed for 3D printing workflows.

### Is Printarr free?

Yes, Printarr is open source and free to use under the MIT license.

### What are the system requirements?

- Docker (any recent version)
- 1GB RAM minimum (2GB+ recommended)
- Storage for your 3D model library
- Internet connection for Telegram

### Does Printarr work on ARM devices (Raspberry Pi)?

Yes! Printarr builds multi-platform images for both amd64 and arm64 architectures.

## Telegram

### Why do I need Telegram API credentials?

Telegram requires API credentials for third-party apps that access its platform. This is how Printarr connects to your account to monitor channels.

### Is my Telegram account safe?

Printarr only reads messages from channels you're a member of. It doesn't send messages, join channels, or access private chats. Your session is stored locally in your config volume.

### Can I use a bot instead of my account?

Currently, Printarr requires a user account. Bots have limited access to channel content and can't download files the same way.

### Do I need Telegram Premium?

No, Printarr works with free Telegram accounts.

### Can others see I'm using Printarr?

Printarr appears as an "Unknown Session" in your Telegram active sessions. Channel admins cannot see you're using it.

## Channels

### How do I find channels to add?

Look for Telegram channels that share 3D-printable content. Many designers and communities share STL files through Telegram. Start with public channels by searching Telegram.

### Can I add private channels?

Yes, but you must already be a member. Use the invite link format (`https://t.me/+abc123`).

### Why isn't a channel showing any designs?

- The channel may not have 3D files
- Backfill may not have completed
- Files may be in unsupported formats
- Check Activity for errors

### How often does Printarr check for new posts?

With live monitoring enabled, new posts appear within seconds. The catch-up sync (for missed messages) runs every 5 minutes by default.

## Downloads

### What file formats are supported?

**3D Files:** STL, 3MF, OBJ, STEP, IGES, FBX, DAE
**Archives:** ZIP, RAR, 7z, TAR, TAR.GZ

### Where are my files downloaded to?

Files are organized in `/library` using the template you configure. Default: `/library/{designer}/{title}/`

### Can I change where files are saved?

Yes, modify `PRINTARR_LIBRARY_TEMPLATE`. Existing files won't move; only new downloads use the new template.

### How do I download everything from a channel?

1. Set the channel to "Auto (All)" mode
2. Start a full backfill
3. All designs will be queued for download

### Why are downloads slow?

Telegram has rate limits. Printarr respects these to avoid bans. Speeds are typically 1-5 MB/s per file.

## Library

### Can I use my existing 3D model folder?

Yes! Mount it as a watch folder (`/watch/existing:ro`) and use bulk import to catalog it.

### Will Printarr move or rename my files?

Only during organized download. Imported files from watch folders can be configured to leave originals in place.

### How do I back up my library?

Your library is in the `/library` volume. Back up this directory using your preferred backup solution. Also back up `/config` for your database and settings.

## Thangs Integration

### What is Thangs?

[Thangs](https://thangs.com) is a search engine for 3D models. Printarr can use it to enrich designs with metadata.

### Why do I need FlareSolverr?

Thangs uses Cloudflare protection. FlareSolverr acts as a proxy to bypass this protection for API requests.

### Is FlareSolverr required?

No, it's optional. Without it, you just won't get Thangs metadata and duplicate detection.

## Google Drive

### Why would I use Google Drive import?

Many designers share files through Google Drive links in addition to Telegram. This lets you import directly.

### Do I need a Google account?

Yes, for OAuth authentication to access private or shared folders.

### Can I use Google Drive without OAuth?

For public folders only, you can use a simple API key instead of OAuth.

## Performance

### How much storage do I need?

Depends on your usage:
- Small collection: 50-100GB
- Medium: 500GB-1TB
- Large: 2TB+

Plus staging space (2-5x your largest download).

### Can I run Printarr on a NAS?

Yes! Many users run it on Synology, QNAP, or Unraid NAS devices.

### How do I limit resource usage?

- Reduce `PRINTARR_MAX_CONCURRENT_DOWNLOADS`
- Disable auto-render
- Increase sync intervals

## Troubleshooting

### Printarr won't start

Check Docker logs: `docker logs printarr`

Common causes:
- Missing environment variables
- Port already in use
- Volume permission issues

### I'm getting rate limited

Lower your rate limits:
```yaml
PRINTARR_TELEGRAM_RATE_LIMIT_RPM: 20
PRINTARR_TELEGRAM_CHANNEL_SPACING: 3.0
```

### Thumbnails aren't generating

Check that stl-thumb is working:
```bash
docker exec printarr stl-thumb --version
```

See [Troubleshooting](troubleshooting.md) for more help.

## Contributing

### How can I contribute?

- Report bugs and request features on GitHub
- Submit pull requests
- Improve documentation
- Share with the 3D printing community

### Where do I report bugs?

[GitHub Issues](https://github.com/AdamA817/printarr/issues)

### Is there a roadmap?

Yes, see [ROADMAP.md](https://github.com/AdamA817/printarr/blob/main/ROADMAP.md) for planned features.
