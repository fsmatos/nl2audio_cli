"""
Pytest configuration and fixtures for nl2audio tests.
"""

import sys
import tempfile
from pathlib import Path

import pytest

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from nl2audio.config import AppConfig, GmailConfig, LoggingConfig, RSSConfig


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@pytest.fixture
def sample_config(temp_dir):
    """Create a sample configuration for testing."""
    return AppConfig(
        output_dir=temp_dir / "output",
        feed_title="Test Feed",
        site_url="http://127.0.0.1:8080",
        tts_provider="openai",
        voice="alloy",
        bitrate="64k",
        max_minutes=60,
        gmail=GmailConfig(
            enabled=True,
            user="test@gmail.com",
            app_password="test_password",
            label="Newsletters",
            method="oauth",
        ),
        rss=RSSConfig(enabled=True, feeds=[]),
        logging=LoggingConfig(level="INFO", enable_file_logging=False, log_file=None),
    )


@pytest.fixture
def mock_env_vars(monkeypatch):
    """Mock environment variables for testing."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test1234567890abcdef")
    monkeypatch.setenv("HOME", str(Path.home()))


@pytest.fixture
def newsletter_html():
    """Load sample newsletter HTML content."""
    fixture_path = Path(__file__).parent / "fixtures" / "newsletter_sample.html"
    return fixture_path.read_text(encoding="utf-8")


@pytest.fixture
def plain_text():
    """Load sample plain text content."""
    fixture_path = Path(__file__).parent / "fixtures" / "plain_text.txt"
    return fixture_path.read_text(encoding="utf-8")


@pytest.fixture
def gmail_message():
    """Load sample Gmail API response."""
    import json

    fixture_path = Path(__file__).parent / "fixtures" / "gmail_message_full.json"
    return json.loads(fixture_path.read_text(encoding="utf-8"))


@pytest.fixture
def mock_ffmpeg(monkeypatch):
    """Mock ffmpeg availability for testing."""

    def mock_which(cmd):
        if cmd == "ffmpeg":
            return "/usr/bin/ffmpeg"
        return None

    monkeypatch.setattr("shutil.which", mock_which)


@pytest.fixture
def mock_openai_client(monkeypatch):
    """Mock OpenAI client for testing."""

    class MockSpeech:
        def create(self, **kwargs):
            # Return mock audio data - create a minimal valid MP3 file
            # This is a very basic MP3 header (not fully compliant but enough for testing)
            mp3_data = (
                b"\xff\xfb\x90\x44"  # MP3 sync word + header
                + b"\x00" * 1000  # Some dummy data
            )

            return type(
                "MockResponse",
                (),
                {"content": mp3_data, "read": lambda *args, **kwargs: mp3_data},
            )()

    class MockAudio:
        def __init__(self):
            self.speech = MockSpeech()

    class MockOpenAIClient:
        def __init__(self, api_key=None):
            self.api_key = api_key
            self.audio = MockAudio()

    # Mock pydub AudioSegment to avoid audio processing issues
    class MockAudioSegment:
        def __init__(self, duration=0):
            self.duration = duration
            # Mock audio properties needed for normalization
            self.max = 0.5  # Mock peak amplitude
            self.max_possible_amplitude = 1.0  # Mock max possible amplitude

        def __len__(self):
            return self.duration

        def __add__(self, other):
            if isinstance(other, MockAudioSegment):
                return MockAudioSegment(self.duration + other.duration)
            return self

        @classmethod
        def from_file(cls, file, format=None, **kwargs):
            # Return a mock audio segment with 1000ms duration
            return cls(1000)

        @classmethod
        def silent(cls, duration=0):
            return cls(duration)

        def apply_gain(self, gain_db):
            # Mock gain application - just return self
            return self

        def export(self, path, format=None, bitrate=None):
            # Mock export - just write some dummy data
            path.write_bytes(b"mock_audio_export")

    monkeypatch.setattr("nl2audio.tts.OpenAI", MockOpenAIClient)
    monkeypatch.setattr("nl2audio.tts.AudioSegment", MockAudioSegment)


@pytest.fixture
def mock_gmail_service(monkeypatch):
    """Mock Gmail service for testing."""

    class MockGmailService:
        def users(self):
            return self

        def labels(self):
            return self

        def list(self, userId):
            return self

        def execute(self):
            return {
                "labels": [
                    {"id": "Label_1", "name": "Newsletters"},
                    {"id": "Label_2", "name": "INBOX"},
                    {"id": "Label_3", "name": "CATEGORY_PERSONAL"},
                ]
            }

    monkeypatch.setattr(
        "nl2audio.gmail_oauth.build", lambda *args, **kwargs: MockGmailService()
    )


@pytest.fixture
def mock_keyring(monkeypatch):
    """Mock keyring for testing."""
    stored_credentials = {}

    def mock_get_password(service, key):
        return stored_credentials.get(f"{service}:{key}")

    def mock_set_password(service, key, password):
        stored_credentials[f"{service}:{key}"] = password

    def mock_delete_password(service, key):
        if f"{service}:{key}" in stored_credentials:
            del stored_credentials[f"{service}:{key}"]

    monkeypatch.setattr("keyring.get_password", mock_get_password)
    monkeypatch.setattr("keyring.set_password", mock_set_password)
    monkeypatch.setattr("keyring.delete_password", mock_delete_password)
