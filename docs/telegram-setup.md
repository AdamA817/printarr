# Telegram Setup

This guide explains how to obtain Telegram API credentials and authenticate Printarr.

## Getting API Credentials

### Step 1: Log in to Telegram

1. Go to [my.telegram.org](https://my.telegram.org)
2. Enter your phone number (with country code, e.g., +1234567890)
3. You'll receive a verification code in Telegram - enter it

### Step 2: Create an Application

1. Click **API development tools**
2. Fill in the application form:
   - **App title**: Printarr (or any name)
   - **Short name**: printarr (lowercase, no spaces)
   - **Platform**: Desktop
   - **Description**: 3D design manager (optional)
3. Click **Create application**

### Step 3: Copy Your Credentials

After creating the app, you'll see:
- **App api_id**: A number like `12345678`
- **App api_hash**: A string like `abcdef1234567890abcdef1234567890`

**Keep these secure!** Anyone with these credentials can access Telegram as your application.

## Configuring Printarr

### Docker Compose

Add to your `.env` file:

```bash
TELEGRAM_API_ID=12345678
TELEGRAM_API_HASH=abcdef1234567890abcdef1234567890
```

Reference in `docker-compose.yml`:

```yaml
environment:
  - PRINTARR_TELEGRAM_API_ID=${TELEGRAM_API_ID}
  - PRINTARR_TELEGRAM_API_HASH=${TELEGRAM_API_HASH}
```

### Docker CLI

Pass directly as environment variables:

```bash
docker run -d \
  -e PRINTARR_TELEGRAM_API_ID=12345678 \
  -e PRINTARR_TELEGRAM_API_HASH=abcdef1234567890 \
  ...
```

## First-Time Authentication

When you first access Printarr, you'll need to authenticate with Telegram:

1. Open the Printarr web UI
2. Click **Connect to Telegram** (or go to Settings > Telegram)
3. Enter your phone number (with country code)
4. Check your Telegram app for a verification code
5. Enter the code in Printarr
6. If you have 2FA enabled, enter your password

After authentication, Printarr stores a session file in `/config`. This session persists across restarts.

## Session Management

### Session Location

The Telegram session is stored at `/config/telegram.session`. This file:
- Contains your authenticated session
- Should be backed up with your config volume
- Is encrypted and tied to your API credentials

### Re-authentication

You may need to re-authenticate if:
- The session file is deleted or corrupted
- You change Telegram API credentials
- Telegram revokes the session (rare)

To re-authenticate:
1. Go to **Settings** > **Telegram**
2. Click **Disconnect**
3. Follow the authentication flow again

### Multiple Instances

Each Printarr instance needs:
- Its own session file (separate `/config` volumes)
- Can share the same API credentials
- Will appear as separate "devices" in Telegram

## Rate Limiting

Telegram has rate limits to prevent abuse. Printarr includes built-in rate limiting:

| Setting | Default | Description |
|---------|---------|-------------|
| `PRINTARR_TELEGRAM_RATE_LIMIT_RPM` | 30 | Requests per minute |
| `PRINTARR_TELEGRAM_CHANNEL_SPACING` | 2.0 | Seconds between channel requests |

### Signs of Rate Limiting

- `FloodWaitError` messages in logs
- Slow or failed channel syncs
- "Too many requests" errors

### Fixing Rate Limits

1. Lower `PRINTARR_TELEGRAM_RATE_LIMIT_RPM` (try 20)
2. Increase `PRINTARR_TELEGRAM_CHANNEL_SPACING` (try 3.0)
3. Reduce `PRINTARR_SYNC_BATCH_SIZE`
4. Wait for the flood wait to expire (usually minutes to hours)

## Security Considerations

### Protect Your Credentials

- Never share your `api_id` and `api_hash`
- Don't commit them to version control
- Use environment variables or secrets management

### Session Security

- The session file grants full access to your Telegram account
- Store it securely (encrypted volume, restricted permissions)
- Revoke sessions if compromised (Telegram Settings > Devices)

### What Printarr Can Access

With your authenticated session, Printarr can:
- Read messages from channels you're a member of
- Download files from those channels
- See your channel list

Printarr does **not**:
- Send messages
- Join/leave channels automatically
- Access private chats
- Modify your account

## Troubleshooting

### "API_ID_INVALID" Error

- Double-check your `api_id` is a number
- Ensure no extra spaces in environment variables

### "API_HASH_INVALID" Error

- Verify the hash is exactly 32 characters
- Check for copy/paste errors

### "PHONE_NUMBER_INVALID" Error

- Include country code (e.g., +1 for US)
- Use digits only, no spaces or dashes

### "SESSION_REVOKED" Error

1. Delete `/config/telegram.session`
2. Restart Printarr
3. Re-authenticate

### Can't Receive Verification Code

- Check Telegram app for the code (not SMS)
- Try requesting a new code
- Ensure your phone number is correct
