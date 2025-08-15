# Security Guide

## Secrets Management

This project follows strict security practices to prevent accidental exposure of sensitive information.

### What Never Gets Committed

- **API Keys**: OpenAI API keys, Gmail app passwords
- **Personal Data**: Email addresses, usernames, home directory paths
- **OAuth Tokens**: Google OAuth credentials, access tokens
- **Local Configuration**: User-specific paths, database files, log files

### Environment Variables

All sensitive configuration is handled via environment variables:

```bash
# Copy the example and fill in your values
cp .env.example .env

# Required variables
export OPENAI_API_KEY="sk-your-key-here"
export GMAIL_USER="your-email@gmail.com"
export GMAIL_APP_PASSWORD="your-16-char-password"
```

### Pre-commit Security Checks

The project uses pre-commit hooks with detect-secrets to prevent accidental commits:

```bash
# Install pre-commit hooks
make setup-dev

# Run security scan
make secrets-baseline

# Check all files before commit
pre-commit run --all-files
```

### If You Accidentally Commit a Secret

**IMMEDIATE ACTION REQUIRED:**

1. **Rotate the exposed secret** in the provider dashboard
2. **Remove from git history** using git filter-repo:

```bash
# Install git-filter-repo
pipx install git-filter-repo  # or brew install git-filter-repo

# Remove specific file from entire history
git filter-repo --invert-paths --path .env --path .env --force

# Or replace specific text across history
git filter-repo --replace-text <(echo 'sk-...==>REDACTED_OPENAI_KEY')

# Force push to all branches and tags
git push --force --all
git push --force --tags
```

3. **Notify team members** to reset their local repositories
4. **Update .secrets.baseline** with `make secrets-baseline`

### Security Best Practices

- Never hardcode secrets in source code
- Use environment variables for all configuration
- Run `pre-commit run -a` before every commit
- Regularly update `.secrets.baseline`
- Report security issues privately to maintainers

### CI/CD Security

GitHub Actions automatically:
- Scans for new secrets using detect-secrets
- Fails builds if secrets are detected
- Runs security checks on every PR and push
