# Google Drive Integration Setup

This guide explains how to configure Google Drive integration for importing 3D designs from Google Drive folders.

## Two Access Methods

Printarr supports two methods for accessing Google Drive:

1. **OAuth (Recommended)** - For private folders, requires user authentication
2. **API Key** - For public folders only, simpler setup

## Method 1: OAuth Setup (Private Folders)

OAuth is required to access private Google Drive folders. This requires creating a Google Cloud project and OAuth credentials.

### Step 1: Create a Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Click "Select a project" → "New Project"
3. Enter project name: `Printarr` (or any name you prefer)
4. Click "Create"

### Step 2: Enable Google Drive API

1. In your project, go to "APIs & Services" → "Library"
2. Search for "Google Drive API"
3. Click on it and press "Enable"

### Step 3: Configure OAuth Consent Screen

1. Go to "APIs & Services" → "OAuth consent screen"
2. Select "External" user type (unless you have Google Workspace)
3. Fill in the required fields:
   - App name: `Printarr`
   - User support email: Your email
   - Developer contact: Your email
4. Click "Save and Continue"
5. On "Scopes", click "Add or Remove Scopes"
   - Add: `https://www.googleapis.com/auth/drive.readonly`
   - Click "Update" → "Save and Continue"
6. On "Test users", add your Google account email
7. Click "Save and Continue"

### Step 4: Create OAuth Credentials

1. Go to "APIs & Services" → "Credentials"
2. Click "Create Credentials" → "OAuth client ID"
3. Application type: "Web application"
4. Name: `Printarr`
5. Add Authorized redirect URIs:
   - For local development: `http://localhost:3333/api/v1/google/oauth/callback`
   - For Unraid: `http://<your-unraid-ip>:3333/api/v1/google/oauth/callback`
6. Click "Create"
7. Copy the **Client ID** and **Client Secret**

### Step 5: Configure Printarr

Add the credentials to your docker-compose.yml or Unraid template:

```yaml
environment:
  - PRINTARR_GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
  - PRINTARR_GOOGLE_CLIENT_SECRET=your-client-secret
```

Or set them in the Unraid template under "Google Client ID" and "Google Client Secret".

### Step 6: Authenticate in Printarr

1. Go to Printarr Settings → Integrations
2. Click "Connect Google Drive"
3. Complete the OAuth flow in the popup
4. Once connected, you can add private Google Drive folders as import sources

## Method 2: API Key Setup (Public Folders Only)

If you only need to access publicly shared Google Drive folders, you can use a simpler API key.

### Step 1: Create API Key

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a project (or use existing)
3. Enable the Google Drive API (see Step 2 above)
4. Go to "APIs & Services" → "Credentials"
5. Click "Create Credentials" → "API Key"
6. Copy the API key
7. (Optional) Click "Edit API key" to restrict it to Google Drive API only

### Step 2: Configure Printarr

Add the API key to your configuration:

```yaml
environment:
  - PRINTARR_GOOGLE_API_KEY=your-api-key
```

### Limitations

- API key can only access **publicly shared** folders
- Folders must be shared with "Anyone with the link"
- For private folders, use OAuth instead

## Environment Variables Reference

| Variable | Description | Required |
|----------|-------------|----------|
| `PRINTARR_GOOGLE_CLIENT_ID` | OAuth Client ID | For private access |
| `PRINTARR_GOOGLE_CLIENT_SECRET` | OAuth Client Secret | For private access |
| `PRINTARR_GOOGLE_API_KEY` | API Key | For public-only access |
| `PRINTARR_GOOGLE_REDIRECT_URI` | OAuth callback URL | Optional (auto-detected) |

## Security Notes

- Never commit credentials to version control
- Use environment variables or Docker secrets
- OAuth tokens are encrypted at rest using the `PRINTARR_ENCRYPTION_KEY`
- Consider restricting API keys to specific APIs in Google Cloud Console
- In production, move your OAuth app out of "Testing" mode if you have many users

## Troubleshooting

### "Access blocked: Printarr has not completed Google verification"

This is expected for unverified apps. Click "Continue" to proceed (only shown for test users).

### "Error 403: access_denied"

Your Google account is not added as a test user. Go to OAuth consent screen → Test users and add your email.

### "Error 400: redirect_uri_mismatch"

The redirect URI in Printarr doesn't match what's configured in Google Cloud. Check:
1. The URL in Google Cloud Console → Credentials → OAuth 2.0 Client
2. Must exactly match (including http vs https, port, and path)

### Token Expired

OAuth tokens are automatically refreshed. If issues persist, disconnect and reconnect Google Drive in Settings.
