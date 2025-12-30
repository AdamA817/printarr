# Telegram Setup Guide

This guide explains how to obtain and configure Telegram API credentials for Printarr.

## Overview

Printarr uses Telegram's MTProto protocol to connect to channels and download 3D printable designs. This requires API credentials from Telegram, which you obtain by registering your own application.

**This is a one-time setup process.**

## Step 1: Get Telegram API Credentials

### 1.1 Go to my.telegram.org

Open [https://my.telegram.org](https://my.telegram.org) in your browser.

### 1.2 Log in with your phone number

- Enter your phone number in international format (e.g., `+1 555 123 4567`)
- You'll receive a confirmation code via Telegram (not SMS)
- Enter the code to log in

### 1.3 Navigate to API Development Tools

Once logged in, click on **"API development tools"**.

### 1.4 Create a new application

Fill in the form:

| Field | Value |
|-------|-------|
| App title | `Printarr` (or any name you prefer) |
| Short name | `printarr` (lowercase, no spaces) |
| URL | Leave blank or enter your server URL |
| Platform | `Other` |
| Description | Optional |

Click **"Create application"**.

### 1.5 Copy your credentials

After creation, you'll see:
- **api_id** - A numeric ID (e.g., `12345678`)
- **api_hash** - A 32-character hexadecimal string

**Save these credentials securely!** You'll need them for the next step.

## Step 2: Configure Printarr

Choose the method that matches your deployment:

### Option A: Docker Compose (Development)

1. Copy the example environment file:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` and add your credentials:
   ```bash
   TELEGRAM_API_ID=12345678
   TELEGRAM_API_HASH=abcdef1234567890abcdef1234567890
   ```

3. Start Printarr:
   ```bash
   docker compose up -d
   ```

### Option B: Unraid Template

1. In the Unraid Docker settings for Printarr, find the environment variables section
2. Set these variables:
   - **Telegram API ID**: Your api_id (e.g., `12345678`)
   - **Telegram API Hash**: Your api_hash

The API Hash field is masked for security.

### Option C: Deploy Script (Manual Deployment)

1. Copy the configuration example:
   ```bash
   cp scripts/deploy.conf.example scripts/deploy.conf
   ```

2. Edit `scripts/deploy.conf`:
   ```bash
   TELEGRAM_API_ID="12345678"
   TELEGRAM_API_HASH="abcdef1234567890abcdef1234567890"
   ```

3. Run the deploy script:
   ```bash
   ./scripts/deploy.sh
   ```

## Step 3: Authenticate with Telegram

After configuring credentials and starting Printarr:

1. Open Printarr in your browser (default: `http://localhost:3333`)
2. Go to **Settings** > **Telegram**
3. Click **Connect to Telegram**
4. Enter your phone number
5. Enter the verification code sent to your Telegram app
6. If you have 2FA enabled, enter your password

Your Telegram session will be saved and persists across container restarts.

## Security Notes

### Protect Your Credentials

- **Never share your api_hash** - It's tied to your Telegram account
- **Never commit credentials to git** - The `.env` file is in `.gitignore` for this reason
- **Use the `.env` file** - Not directly in docker-compose.yml

### Session File Security

- The Telegram session file is stored in `/config/telegram.session`
- This file allows access to your Telegram account
- Keep your `/config` volume secure
- Don't share or expose this file

### Account Safety

- Printarr uses a **user session**, not a bot
- This means it acts as your Telegram account
- Only monitor channels you have legitimate access to
- Respect Telegram's Terms of Service

## Common Issues

### "App not found" error

- Try a different app title/short name
- Some names may be reserved or already taken
- Use simple alphanumeric names without special characters

### Rate limits when creating apps

- Telegram limits how often you can create applications
- Wait a few hours and try again
- You only need to create the app once

### Phone number format issues

- Use international format with country code (e.g., `+1` for USA)
- Don't include spaces or dashes in some cases
- Try with and without the `+` sign

### "Session expired" or "Auth key error"

- Delete the session file and re-authenticate:
  ```bash
  rm /config/telegram.session
  ```
- Restart Printarr and authenticate again

### "Connection refused" or timeout

- Check your internet connection
- Telegram may be blocked in your region (consider VPN)
- Verify firewall isn't blocking outbound connections

## Environment Variables Reference

| Variable | Required | Description |
|----------|----------|-------------|
| `TELEGRAM_API_ID` | Yes | Numeric API ID from my.telegram.org |
| `TELEGRAM_API_HASH` | Yes | 32-character API hash from my.telegram.org |

## Further Reading

- [Telegram MTProto API Documentation](https://core.telegram.org/mtproto)
- [Telethon Documentation](https://docs.telethon.dev/)
- [Printarr Docker Configuration](DOCKER.md)
