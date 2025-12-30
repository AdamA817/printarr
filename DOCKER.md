# DOCKER (Unraid Deployment)

This document describes container expectations for an Unraid-friendly deployment.
It does not mandate a specific implementation language.

---

## 1. Container Characteristics

- Single Docker image containing:
  - Web UI + API server
  - Background workers (ingestion, download/import, previews)
- Must run correctly behind Unraid’s typical reverse proxy setups (optional).
- Must persist all state in mounted volumes.

---

## 2. Required Volume Mounts

Recommended mounts (host paths are examples):

- `/config`  
  - Telegram session, app config, secrets
  - Example host path: `/mnt/user/appdata/telegram-3d-catalog/config`

- `/data`  
  - Database and internal state
  - Example host path: `/mnt/user/appdata/telegram-3d-catalog/data`

- `/staging`  
  - Temporary downloads and extraction workspace
  - Example host path: `/mnt/user/downloads/telegram-3d-staging`

- `/library`  
  - Final organized library
  - Example host path: `/mnt/user/3d-library`

- `/cache`  
  - Thumbnails, rendered previews, derived artifacts
  - Example host path: `/mnt/user/appdata/telegram-3d-catalog/cache`

---

## 3. Environment Variables

### 3.1 Networking
- `APP_PORT` (default: 7878-like; any free port)
- `BASE_URL` (optional; for reverse proxy)

### 3.2 Storage Paths (inside container)
- `PATH_CONFIG=/config`
- `PATH_DATA=/data`
- `PATH_STAGING=/staging`
- `PATH_LIBRARY=/library`
- `PATH_CACHE=/cache`

### 3.3 Telegram
- `TELEGRAM_SESSION_DIR=/config/telegram`
- `TELEGRAM_DEVICE_NAME` (optional)
- `TELEGRAM_APP_ID` / `TELEGRAM_APP_HASH` (if required by the chosen client library)

> Note: Some MTProto client approaches require an API ID/HASH (Telegram developer credentials).
> If required, the app must provide clear UI guidance and store these securely in `/config`.

### 3.4 Download/Worker Controls
- `MAX_CONCURRENT_DOWNLOADS` (default: 2–4)
- `MAX_CONCURRENT_EXTRACTS` (default: 1–2)
- `MAX_CONCURRENT_RENDERS` (default: 1)
- `JOB_RETRY_MAX` (default: 5)

### 3.5 Backfill Defaults
- `DEFAULT_BACKFILL_MODE` (ALL_HISTORY | LAST_N_MESSAGES | LAST_N_DAYS)
- `DEFAULT_BACKFILL_VALUE` (int)

### 3.6 Library Templates
- `LIBRARY_TEMPLATE_GLOBAL`  
  Default: `/<DesignerOrUnknown>/<Channel>/<DesignTitle>/`
- `DESIGNER_UNKNOWN_VALUE` (default: `Unknown`)

---

## 4. Ports

- Container should expose a single port for UI/API (e.g., `7878/tcp`).
- All worker processes should be internal.

---

## 5. Health & Readiness

- `/api/health` endpoint should return:
  - app version
  - DB connectivity
  - worker heartbeat timestamps
  - telegram session status (connected / needs login)

Unraid templates often benefit from a basic healthcheck.

---

## 6. First-Run Flow Expectations

1) Container starts with no Telegram session
2) UI displays “Telegram not connected” state
3) User initiates login:
   - phone number
   - code
   - optional 2FA password
4) Session is saved to `/config/telegram`
5) User adds channel links
6) Backfill jobs begin

---

## 7. Example `docker run` (illustrative)

```bash
docker run -d \
  --name=telegram-3d-catalog \
  -p 7878:7878 \
  -e APP_PORT=7878 \
  -e PATH_CONFIG=/config \
  -e PATH_DATA=/data \
  -e PATH_STAGING=/staging \
  -e PATH_LIBRARY=/library \
  -e PATH_CACHE=/cache \
  -e MAX_CONCURRENT_DOWNLOADS=3 \
  -v /mnt/user/appdata/telegram-3d-catalog/config:/config \
  -v /mnt/user/appdata/telegram-3d-catalog/data:/data \
  -v /mnt/user/downloads/telegram-3d-staging:/staging \
  -v /mnt/user/3d-library:/library \
  -v /mnt/user/appdata/telegram-3d-catalog/cache:/cache \
  telegram-3d-catalog:latest
```

---

## 8. Unraid Template Notes

- Provide Unraid template fields for:
  - Library path
  - Staging path
  - Config/Data/Cache paths
  - Port mapping
  - Concurrency knobs
- Make sure default internal paths are stable so upgrades don’t break mounts.
