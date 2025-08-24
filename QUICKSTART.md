# nl2audio CLI Quickstart Guide

Turn newsletters into a private podcast with Gmail OAuth and IMAP support.

## Installation

```bash
# Clone and install in editable mode
git clone <your-repo>
cd nl2audio_cli

# Create and activate virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate

# Install the tool in editable mode
pip install -e .

# Verify installation
nl2audio --help
```

**Note**: Virtual environments (venv) are strongly recommended to avoid dependency conflicts with your system Python. The tool will only work when the venv is activated.

## Prerequisites

- **Python 3.11+**
- **ffmpeg** installed and on PATH
- **OpenAI API key** in environment: `export OPENAI_API_KEY=your_key_here`

## Security Setup

**⚠️ IMPORTANT: Never commit secrets or personal data to git!**

1. **Copy environment template:**
```bash
cp .env.example .env
```

2. **Edit .env with your actual values:**
```bash
# OpenAI API key (required)
OPENAI_API_KEY=sk-your-actual-key-here

# Gmail credentials (if using Gmail)
GMAIL_USER=your-email@gmail.com
GMAIL_APP_PASSWORD=your-16-char-app-password

# Optional: Customize output directory
NL2AUDIO_OUTPUT_DIR=~/NewsletterCast
```

3. **Install security hooks (recommended):**
```bash
make setup-dev
```

**Security Notes:**
- The `.env` file is automatically ignored by git
- Gmail OAuth tokens are stored securely in your system keyring
- Never commit `~/.nl2audio/google_client.json` or any credential files
- Run `pre-commit run -a` before committing to catch security issues

## Virtual Environment Management

```bash
# Activate venv before using the tool
cd /path/to/nl2audio_cli
source venv/bin/activate

# Verify it's active (you'll see (venv) in your prompt)
which python  # Should point to venv/bin/python

# Deactivate when done (optional)
deactivate
```

**Important**: The `nl2audio` command only works when the virtual environment is activated. You'll see `(venv)` in your terminal prompt when it's active.

## First Run Setup

```bash
# Initialize configuration
nl2audio init

# Run health checks
nl2audio doctor

# Check specific services
nl2audio doctor --probe-openai
nl2audio doctor --probe-gmail
```

## Configuration Files

- **Config**: `~/.nl2audio/config.toml`
- **Gmail OAuth credentials**: `~/.nl2audio/google_client.json`
- **Output directory**: `~/NewsletterCast/` (default)
- **Database**: `~/NewsletterCast/db.sqlite`
- **Episodes**: `~/NewsletterCast/episodes/`
- **Feed**: `~/NewsletterCast/feed.xml`
- **Logs**: `~/NewsletterCast/nl2audio.log`

**New Prep Configuration:**
```toml
# ~/.nl2audio/config.toml
[prep]
enabled = false                    # Enable/disable prep LLM
model = "gpt-3.5-turbo"          # LLM model to use
temperature = 0.3                 # Creativity level (0.0-2.0)
max_tokens = 2000                 # Maximum tokens per request
```

## Gmail OAuth Setup

```bash
# Connect Gmail account (opens browser for OAuth)
nl2audio connect-gmail

# Test connection and list messages
nl2audio gmail-test

# Fetch emails from Gmail (processes "Newsletters" label by default)
nl2audio fetch-email
```

**Note**: OAuth credentials are stored securely in your system keyring.

**IMAP Fallback**: If OAuth doesn't work, you can use IMAP by setting `gmail.method = "imap"` in your config file and providing an app password.

## Adding Episodes

```bash
# From local file
nl2audio add --source ./newsletter.txt --title "Weekly Update"

# From URL (auto-extracts readable content)
nl2audio add --source "https://example.com/newsletter" --title "Monthly Digest"

# From stdin
echo "Newsletter content" | nl2audio add --source - --title "Direct Input"

# With LLM prep for better TTS quality
nl2audio add --prep --model gpt-4o --source ./newsletter.txt --title "Enhanced Weekly Update"

# From Gmail (auto-fetches and processes)
nl2audio fetch-email

# From Gmail with LLM prep enabled
nl2audio fetch-email --prep --model gpt-3.5-turbo
```

## LLM Text Preparation (Optional)

The prep LLM step optimizes newsletter text for better TTS quality by:
- Fixing formatting issues and improving sentence flow
- Making text more conversational and read-aloud friendly
- Preserving content while enhancing readability

**CLI Flags:**
- `--prep`: Enable LLM prep step
- `--model`: Choose LLM model (gpt-3.5-turbo or gpt-4o)

**Configuration (optional):**
```toml
[prep]
enabled = false                    # Default: disabled
model = "gpt-3.5-turbo"          # Default: gpt-3.5-turbo
temperature = 0.3                 # Default: 0.3 (0.0-2.0)
max_tokens = 2000                 # Default: 2000 (100-4000)
```

**Precedence:** CLI flags > config file > defaults

**Example Usage:**
```bash
# Use CLI flags (overrides config)
nl2audio add --prep --model gpt-4o -s newsletter.txt

# Use config settings
# (set enabled = true in ~/.nl2audio/config.toml)
nl2audio add -s newsletter.txt

# Disable prep even if enabled in config
nl2audio add --prep false -s newsletter.txt
```

**Note:** If the LLM prep fails, the original text is preserved and a warning is logged.

## Podcast Feed Management

```bash
# Generate RSS feed from episodes
nl2audio gen-feed

# Serve locally for podcast app subscription
nl2audio serve --port 8080

# Subscribe in podcast app to: http://127.0.0.1:8080/feed.xml
```

## Daily Automation

```bash
#!/bin/bash
# ~/bin/fetch-newsletters.sh
set -euo pipefail

cd ~/nl2audio_cli
source venv/bin/activate  # CRITICAL: Must activate venv

# Ensure ffmpeg is available
if ! command -v ffmpeg &> /dev/null; then
    echo "Error: ffmpeg not found on PATH"
    exit 1
fi

nl2audio fetch-email
nl2audio gen-feed
```

**Crontab entry** (runs daily at 9 AM):
```bash
0 9 * * * ~/bin/fetch-newsletters.sh >> ~/nl2audio.log 2>&1
```

## Useful Flags & Options

```bash
# Debug mode with verbose logging
nl2audio --debug <command>

# Test specific services
nl2audio doctor --probe-openai --probe-gmail

# Custom port for serving
nl2audio serve --port 9000

# Custom episode title
nl2audio add --source file.txt --title "Custom Title"
```

## Common Issues & Fixes

| Issue | Solution |
|-------|----------|
| **Command not found: nl2audio** | Activate venv: `source venv/bin/activate` |
| **Gmail OAuth disabled** | Run `nl2audio connect-gmail` |
| **API key missing** | `export OPENAI_API_KEY=your_key` |
| **ffmpeg not found** | Install ffmpeg: `brew install ffmpeg` (macOS) |
| **No episodes found** | Check `nl2audio doctor` output |
| **Permission denied** | Check file permissions and keyring access |
| **Import errors** | Ensure venv is activated and reinstall: `pip install -e .` |

## CLI Commands Reference

```bash
nl2audio init          # Create default config
nl2audio doctor        # Comprehensive health checks
nl2audio add           # Add episode from source
nl2audio gen-feed      # Generate RSS feed
nl2audio serve         # Serve podcast locally
nl2audio fetch-email   # Process Gmail newsletters
nl2audio connect-gmail # Setup Gmail OAuth
nl2audio gmail-test    # Test Gmail connection
nl2audio quickstart    # Display this quickstart guide

# New prep LLM flags (available with add and fetch-email):
--prep                 # Enable LLM text preparation
--model MODEL          # Choose LLM model (gpt-3.5-turbo or gpt-4o)
```

## Reset & Troubleshooting

```bash
# Clear configuration
rm -rf ~/.nl2audio/

# Clear keyring tokens
keyring delete nl2audio "gmail:<email>"

# Reset output directory
rm -rf ~/NewsletterCast/

# Reinitialize everything
nl2audio init
nl2audio doctor
```

## Help & Discovery

```bash
# General help
nl2audio --help

# Command-specific help
nl2audio add --help
nl2audio doctor --help
nl2audio serve --help

# Display quickstart guide
nl2audio quickstart
```

## Environment Variables

```bash
# Required
export OPENAI_API_KEY=sk-...

# Optional
export NL2AUDIO_DEBUG=1          # Enable debug logging
export NL2AUDIO_OUTPUT_DIR=/path # Custom output directory
```

## Advanced: Alternatives to Virtual Environment

```bash
# Option 1: Global installation (not recommended)
sudo pip3 install -e .

# Option 2: Use pipx for isolated global install
brew install pipx
pipx install -e .

# Option 3: Add venv to PATH permanently
echo 'export PATH="/path/to/nl2audio_cli/venv/bin:$PATH"' >> ~/.zshrc
```

**Note**: Virtual environments remain the recommended approach for development and avoiding system conflicts.

---

**Need help?** Run `nl2audio doctor` for comprehensive diagnostics.

---

**Personal Use & Copyright**: This tool is provided for personal, non-commercial use. Please respect the terms of service of the APIs and services you connect to. The nl2audio CLI is designed to help you create private podcast content from your own newsletters and content sources.
