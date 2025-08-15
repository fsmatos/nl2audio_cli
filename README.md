# nl2audio (V1 scaffold)

A tiny CLI that converts newsletter text or HTML into MP3 and generates a private podcast RSS.

## Quickstart

1) **Prereqs**
- Python 3.11+
- `ffmpeg` installed and on PATH
- `OPENAI_API_KEY` in your environment

2) **Install (editable)**
```bash
pip install -e .
```

3) **Setup environment**
```bash
# Copy example environment file
cp .env.example .env

# Edit .env with your actual values
# OPENAI_API_KEY=sk-your-key-here
# GMAIL_USER=your-email@gmail.com
# GMAIL_APP_PASSWORD=your-app-password
```

4) **Init config**
```bash
nl2audio init
```

5) **Add an episode**
```bash
# from a text file
nl2audio add --source ./example.txt --title "Example Newsletter"

# from a URL (will fetch & extract readable text)
nl2audio add --source "https://example.com/article" --title "Article Episode"
```

6) **Generate feed + serve locally**
```bash
nl2audio gen-feed
nl2audio serve --port 8080
# subscribe in your podcast app to: http://127.0.0.1:8080/feed.xml
```

## Security & Safety

**⚠️ Never commit secrets or personal data!**

- Copy `.env.example` to `.env` and fill in your values
- The `.env` file is automatically ignored by git
- Run `make setup-dev` to install security hooks
- Use `pre-commit run -a` before committing

See [docs/SECURITY.md](docs/SECURITY.md) for detailed security guidelines.

## Development

```bash
# Setup development environment
make setup-dev

# Format code
make format

# Run tests
make test

# Run all checks
make pre-commit-all
```

> Personal-use only. Respect copyright. This is an early scaffold.
