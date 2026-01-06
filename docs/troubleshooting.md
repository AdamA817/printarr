# Troubleshooting

Common issues and how to resolve them.

## Connection Issues

### Telegram Won't Connect

**Symptoms:**
- "Disconnected" status in Settings
- Login fails repeatedly

**Solutions:**
1. Verify API credentials are correct
2. Check internet connectivity
3. Try deleting session file: `rm /config/telegram.session`
4. Restart container and re-authenticate

### "FloodWaitError" in Logs

**Cause:** Too many requests to Telegram API

**Solutions:**
1. Lower `PRINTARR_TELEGRAM_RATE_LIMIT_RPM` (try 20)
2. Increase `PRINTARR_TELEGRAM_CHANNEL_SPACING` (try 3-5)
3. Wait for the flood wait to expire (time shown in logs)
4. Reduce `PRINTARR_SYNC_BATCH_SIZE`

### "SessionExpired" or "AuthKeyDuplicated"

**Cause:** Session invalidated by Telegram

**Solutions:**
1. Delete `/config/telegram.session`
2. Restart Printarr
3. Re-authenticate with Telegram

## Download Issues

### Downloads Stuck in Queue

**Check:**
1. Telegram connection status (Settings > Telegram)
2. Worker logs for errors: `docker logs printarr`
3. Rate limit status

**Solutions:**
1. Restart the container
2. Cancel and retry stuck jobs
3. Check for flood wait errors

### "File Not Found" Errors

**Causes:**
- Original message deleted
- File expired on Telegram servers
- Channel access revoked

**Solutions:**
1. Re-sync the channel to get updated file references
2. Check if you're still a member of private channels
3. Remove the design if source is gone

### Archive Extraction Fails

**Causes:**
- Corrupted archive
- Password-protected archive
- Unsupported format
- Disk full

**Solutions:**
1. Check available space in `/staging`
2. Try downloading manually to test file
3. Check logs for specific error
4. Password archives must be extracted manually

### Wrong Files Downloaded

**Cause:** Design linked to wrong Telegram message

**Solutions:**
1. Delete design and re-sync channel
2. Manually update file links (if available)
3. Report issue if consistent

## UI Issues

### Page Won't Load

**Check:**
1. Container is running: `docker ps | grep printarr`
2. Port is accessible: `curl http://localhost:3333/api/health`
3. Browser console for JavaScript errors

**Solutions:**
1. Clear browser cache
2. Try different browser
3. Check container logs for errors
4. Restart container

### Real-time Updates Not Working

**Cause:** Server-Sent Events connection failed

**Solutions:**
1. Check browser console for connection errors
2. Verify no proxy is blocking SSE
3. Refresh the page
4. Check reverse proxy configuration

### Missing Thumbnails

**Causes:**
- Render job failed
- Cache cleared
- stl-thumb not working

**Solutions:**
1. Check Activity for failed render jobs
2. Manually trigger re-render
3. Check logs for stl-thumb errors
4. Verify OpenGL libraries are installed (container issue)

## Database Issues

### "Database is Locked"

**Cause:** Multiple processes accessing SQLite

**Solutions:**
1. Ensure only one Printarr instance uses the config volume
2. Restart container
3. Check for zombie processes

### Database Corruption

**Symptoms:**
- Errors about malformed database
- Missing data

**Solutions:**
1. Stop Printarr
2. Backup `/config/printarr.db`
3. Try: `sqlite3 /config/printarr.db "PRAGMA integrity_check;"`
4. If corrupt, restore from backup or reset

### Migration Errors

**Symptoms:**
- Startup fails with migration error
- Database schema mismatch

**Solutions:**
1. Check logs for specific error
2. Backup database before fixing
3. Report issue with logs on GitHub

## Performance Issues

### High CPU Usage

**Causes:**
- Too many concurrent operations
- Preview rendering
- Large sync batches

**Solutions:**
1. Lower `PRINTARR_MAX_CONCURRENT_DOWNLOADS`
2. Disable auto-render or lower priority
3. Reduce `PRINTARR_SYNC_BATCH_SIZE`

### High Memory Usage

**Causes:**
- Large file processing
- Memory leaks (please report)

**Solutions:**
1. Restart container periodically
2. Limit concurrent operations
3. Add memory limits to container

### Slow Disk I/O

**Causes:**
- Staging on slow storage
- Many small file operations

**Solutions:**
1. Move `/staging` to SSD
2. Use tmpfs for staging (if sufficient RAM)
3. Reduce concurrent downloads

## Log Locations

### Container Logs

```bash
docker logs printarr
docker logs printarr --tail 100 -f  # Follow last 100 lines
```

### Application Logs

Inside container:
- `/config/logs/printarr.log` (if file logging enabled)

### Health Check

```bash
curl http://localhost:3333/api/health
# Returns: {"status":"ok","version":"1.0.0","database":"connected"}
```

### Detailed Health

```bash
curl http://localhost:3333/api/health/detailed
# Returns detailed component status
```

## Getting Help

### Before Reporting

1. Check this troubleshooting guide
2. Search existing [GitHub Issues](https://github.com/AdamA817/printarr/issues)
3. Collect relevant logs

### Reporting an Issue

Include:
1. Printarr version (`/api/health`)
2. Docker/environment info
3. Steps to reproduce
4. Relevant log snippets
5. Expected vs actual behavior

### Log Privacy

Before sharing logs:
- Remove API credentials
- Redact phone numbers
- Remove personal file paths if sensitive
