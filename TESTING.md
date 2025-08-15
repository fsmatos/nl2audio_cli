# Testing Guide for nl2audio_cli

This document outlines both manual and automated testing procedures for the nl2audio CLI application.

## Manual Testing Checklist

### Prerequisites
- Python 3.11+ installed
- ffmpeg available in PATH
- Valid OPENAI_API_KEY in environment
- Google Cloud OAuth credentials (for Gmail testing)

### Setup & Configuration
- [ ] **`nl2audio init`**
  - Expected: Creates `~/.nl2audio/config.toml`
  - Expected: Sets default output directory to `~/NewsletterCast`
  - Expected: Configures Gmail with `method="app_password"` by default

- [ ] **Environment Validation**
  - Expected: `nl2audio doctor` shows OPENAI_API_KEY as valid
  - Expected: ffmpeg check passes
  - Expected: Output directory is writable

### Gmail Integration (OAuth)
- [ ] **`nl2audio connect-gmail`**
  - Expected: Opens browser for OAuth flow
  - Expected: Stores tokens securely in keyring
  - Expected: Updates config to `gmail.method="oauth"`
  - Expected: Shows success message with user email

- [ ] **`nl2audio gmail-test`**
  - Expected: Connects to Gmail API successfully
  - Expected: Finds "Newsletters" label (or shows available labels)
  - Expected: Lists up to 5 messages with subjects
  - Expected: Prefers HTML content over plain text

- [ ] **`nl2audio fetch-email`**
  - Expected: Processes emails from configured label
  - Expected: Extracts readable content (HTML preferred)
  - Expected: Creates EmailResult objects with title, text, source

### Core Functionality
- [ ] **`nl2audio add --source test.txt --title "Test Episode"`**
  - Expected: Reads source file successfully
  - Expected: Creates episode entry in database
  - Expected: Shows processing progress

- [ ] **`nl2audio gen-feed`**
  - Expected: Generates `feed.xml` in output directory
  - Expected: RSS feed contains episode metadata
  - Expected: Valid XML structure

- [ ] **`nl2audio serve --port 8080`**
  - Expected: Starts HTTP server on port 8080
  - Expected: Serves feed at `http://127.0.0.1:8080/feed.xml`
  - Expected: Serves episode files at `/episodes/`
  - Expected: Podcast app can subscribe to feed

### Error Handling
- [ ] **Invalid Gmail credentials**
  - Expected: Clear error message directing to `nl2audio doctor`
  - Expected: Suggests running `nl2audio connect-gmail`

- [ ] **Missing label**
  - Expected: Shows available labels
  - Expected: Continues gracefully

- [ ] **Invalid source file**
  - Expected: Descriptive error message
  - Expected: Suggests troubleshooting steps

## Automated Testing

### Running Tests
```bash
# Install test dependencies
pip install pytest pytest-mock pytest-cov

# Run all tests
pytest

# Run with coverage
pytest --cov=nl2audio

# Run specific test file
pytest tests/test_gmail_oauth_stub.py
```

### Test Categories
1. **Unit Tests**: Individual function testing with mocked dependencies
2. **Integration Tests**: Database and file system operations
3. **Mock Tests**: External API calls (OpenAI, Gmail) without real requests
4. **Validation Tests**: Configuration and input validation

### Test Data
- Sample newsletters in `tests/fixtures/`
- Mock Gmail API responses
- Temporary test databases
- Isolated test directories

## Troubleshooting

### Common Issues
1. **OAuth Flow Fails**
   - Check Google Cloud Console credentials
   - Verify OAuth consent screen configuration
   - Clear stored tokens: `keyring delete nl2audio gmail:temp`

2. **Gmail Label Not Found**
   - Run `nl2audio gmail-test` to see available labels
   - Update config with correct label name
   - Create "Newsletters" label in Gmail if needed

3. **Database Errors**
   - Check output directory permissions
   - Verify SQLite is working: `python -c "import sqlite3; print('OK')"`

### Getting Help
- Run `nl2audio doctor` for comprehensive health check
- Check logs in output directory
- Use `--debug` flag for verbose output
- Review `nl2audio doctor --probe-openai --probe-gmail` for API connectivity
