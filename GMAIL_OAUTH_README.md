# Gmail OAuth Setup for nl2audio

This document explains how to set up Gmail OAuth authentication for the `nl2audio` CLI tool.

## Overview

The `nl2audio` CLI now supports two Gmail authentication methods:
1. **OAuth 2.0** (recommended) - More secure, no app passwords needed
2. **IMAP with App Password** (fallback) - Traditional method using app passwords

## Prerequisites

1. **Google Cloud Project**: You need a Google Cloud project with the Gmail API enabled
2. **OAuth 2.0 Client ID**: A desktop OAuth 2.0 client ID configured
3. **Python Dependencies**: The required packages are automatically installed

## Step 1: Set up Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Enable the Gmail API:
   - Go to "APIs & Services" > "Library"
   - Search for "Gmail API"
   - Click "Enable"

## Step 2: Create OAuth 2.0 Credentials

1. Go to "APIs & Services" > "Credentials"
2. Click "Create Credentials" > "OAuth 2.0 Client IDs"
3. Choose "Desktop application" as the application type
4. Give it a name (e.g., "nl2audio CLI")
5. Download the JSON file (it will be named something like `client_secret_XXXXX.json`)

## Step 3: Install the Credentials

1. Copy the downloaded JSON file to `~/.nl2audio/google_client.json`
2. Ensure the file has the correct permissions:
   ```bash
   chmod 600 ~/.nl2audio/google_client.json
   ```

## Step 4: Authenticate with Gmail

Run the OAuth authentication command:

```bash
nl2audio connect-gmail
```

This will:
1. Open your default web browser for OAuth authentication
2. Ask you to sign in to your Google account
3. Request permission to access your Gmail (read-only)
4. Store the credentials securely in your system keychain
5. Update your configuration to use OAuth

**Note**: If the browser doesn't open automatically, the command will fall back to a console-based authentication flow.

## Step 5: Test the Connection

Test that OAuth is working correctly:

```bash
nl2audio gmail-test
```

This command will:
1. Connect to Gmail using OAuth
2. List up to 5 messages from your configured "Newsletters" label
3. Verify that the authentication and API calls are working

## Configuration

After successful OAuth authentication, your `~/.nl2audio/config.toml` will be updated:

```toml
[gmail]
enabled = true
user = "your.email@gmail.com"
method = "oauth"
app_password = ""  # Cleared when using OAuth
label = "Newsletters"
```

## Using OAuth with Existing Commands

Once OAuth is configured, all existing Gmail commands will automatically use OAuth:

- `nl2audio fetch-email` - Fetches emails using OAuth
- `nl2audio doctor --probe-gmail` - Tests OAuth connectivity
- `nl2audio gmail-test` - Tests OAuth and lists messages

## Fallback to IMAP

If OAuth fails for any reason, the system will automatically fall back to IMAP (if configured):

1. Set `method = "app_password"` in your config
2. Ensure `app_password` is set to a valid Gmail app password
3. The system will use IMAP instead of OAuth

## Troubleshooting

### Common Issues

1. **"OAuth client secrets file not found"**
   - Ensure `~/.nl2audio/google_client.json` exists
   - Check file permissions (should be 600)

2. **"No valid OAuth credentials found"**
   - Run `nl2audio connect-gmail` to authenticate
   - Check if your system keychain is accessible

3. **"OAuth authentication failed"**
   - Verify your Google Cloud project has Gmail API enabled
   - Check that your OAuth client ID is configured for desktop applications
   - Ensure you're using the correct Google account

4. **Browser doesn't open for OAuth**
   - The command will automatically fall back to console-based authentication
   - Copy and paste the authorization URL into your browser manually

### Keyring Issues

If you encounter keyring-related errors:

1. **macOS**: The system keychain should work automatically
2. **Linux**: Install `gnome-keyring` or `kwallet`
3. **Windows**: The Windows Credential Manager should work automatically

### Re-authenticating

If you need to re-authenticate:

1. Remove stored credentials:
   ```bash
   keyring delete "nl2audio" "gmail:your.email@gmail.com"
   ```
2. Run `nl2audio connect-gmail` again

## Security Features

- **Read-only access**: The OAuth scope only requests read access to Gmail
- **Secure storage**: Credentials are stored in your system's secure keychain
- **Automatic refresh**: Tokens are automatically refreshed when needed
- **No password storage**: No passwords are stored in plain text

## API Scopes

The OAuth flow requests the following scope:
- `https://www.googleapis.com/auth/gmail.readonly` - Read-only access to Gmail

This scope allows the tool to:
- Read email messages
- List labels and folders
- Access message metadata
- **Cannot** send emails, modify messages, or access other Google services

## Migration from IMAP

If you're currently using IMAP with app passwords:

1. Run `nl2audio connect-gmail` to set up OAuth
2. Your configuration will be automatically updated
3. The old app password will be cleared
4. All existing functionality will continue to work

## Support

If you encounter issues:

1. Check the troubleshooting section above
2. Run `nl2audio doctor --probe-gmail` for diagnostic information
3. Check the logs for detailed error messages
4. Ensure all dependencies are properly installed
