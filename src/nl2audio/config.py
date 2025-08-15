from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

import tomlkit
from dotenv import load_dotenv

load_dotenv()

DEFAULT_DIR = Path(os.path.expanduser("~")) / "NewsletterCast"
CONFIG_PATH = Path(os.path.expanduser("~")) / ".nl2audio" / "config.toml"


@dataclass
class GmailConfig:
    enabled: bool = False
    user: str = ""
    app_password: str = ""
    label: str = "Newsletters"
    method: str = "app_password"  # "oauth" or "app_password"


@dataclass
class RSSConfig:
    enabled: bool = False
    feeds: list[str] = field(default_factory=list)  # ✅ use default_factory


@dataclass
class LoggingConfig:
    level: str = "INFO"
    enable_file_logging: bool = True
    log_file: Optional[str] = None  # If None, will use default location


@dataclass
class AppConfig:
    output_dir: Path = DEFAULT_DIR
    feed_title: str = "My Newsletters"
    site_url: str = "http://127.0.0.1:8080"
    tts_provider: str = "openai"
    voice: str = "alloy"
    bitrate: str = "64k"
    max_minutes: int = 60
    gmail: GmailConfig = field(default_factory=GmailConfig)  # ✅
    rss: RSSConfig = field(default_factory=RSSConfig)  # ✅
    logging: LoggingConfig = field(default_factory=LoggingConfig)  # ✅


def ensure_config() -> AppConfig:
    if not CONFIG_PATH.exists():
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        cfg = AppConfig()
        save_config(cfg)
        return cfg
    return load_config()


def load_config() -> AppConfig:
    if not CONFIG_PATH.exists():
        return AppConfig()
    text = CONFIG_PATH.read_text(encoding="utf-8")
    data = tomlkit.parse(text)

    # Simple, forgiving loader
    def get(d, k, default):
        return d[k] if k in d and d[k] is not None else default

    gmail_d = get(data, "gmail", {})
    rss_d = get(data, "rss", {})
    logging_d = get(data, "logging", {})

    # Priority: Environment variables > Config file > Defaults
    output_dir = os.getenv("NL2AUDIO_OUTPUT_DIR") or get(
        data, "output_dir", str(DEFAULT_DIR)
    )
    feed_title = os.getenv("NL2AUDIO_FEED_TITLE") or get(
        data, "feed_title", "My Newsletters"
    )
    site_url = os.getenv("NL2AUDIO_SITE_URL") or get(
        data, "site_url", "http://127.0.0.1:8080"
    )
    tts_provider = os.getenv("NL2AUDIO_TTS_PROVIDER") or get(
        data, "tts_provider", "openai"
    )
    voice = os.getenv("NL2AUDIO_VOICE") or get(data, "voice", "alloy")
    bitrate = os.getenv("NL2AUDIO_BITRATE") or get(data, "bitrate", "64k")
    max_minutes = int(os.getenv("NL2AUDIO_MAX_MINUTES") or get(data, "max_minutes", 60))

    # Gmail config with environment variable priority
    gmail_user = os.getenv("GMAIL_USER") or get(gmail_d, "user", "")
    gmail_app_password = os.getenv("GMAIL_APP_PASSWORD") or get(
        gmail_d, "app_password", ""
    )
    gmail_label = os.getenv("GMAIL_LABEL") or get(gmail_d, "label", "Newsletters")

    # Logging config with environment variable priority
    log_level = os.getenv("NL2AUDIO_LOG_LEVEL") or get(logging_d, "level", "INFO")
    enable_file_logging = os.getenv(
        "NL2AUDIO_ENABLE_FILE_LOGGING", "true"
    ).lower() == "true" or get(logging_d, "enable_file_logging", True)

    return AppConfig(
        output_dir=Path(output_dir).expanduser(),
        feed_title=feed_title,
        site_url=site_url,
        tts_provider=tts_provider,
        voice=voice,
        bitrate=bitrate,
        max_minutes=max_minutes,
        gmail=GmailConfig(
            enabled=bool(get(gmail_d, "enabled", False)),
            user=gmail_user,
            app_password=gmail_app_password,
            label=gmail_label,
            method=get(gmail_d, "method", "app_password"),
        ),
        rss=RSSConfig(
            enabled=bool(get(rss_d, "enabled", False)),
            feeds=list(get(rss_d, "feeds", []) or []),
        ),
        logging=LoggingConfig(
            level=log_level,
            enable_file_logging=enable_file_logging,
            log_file=get(logging_d, "log_file", None),
        ),
    )


def save_config(cfg: AppConfig) -> None:
    doc = tomlkit.document()
    doc.add("output_dir", str(cfg.output_dir))
    doc.add("feed_title", cfg.feed_title)
    doc.add("site_url", cfg.site_url)
    doc.add("tts_provider", cfg.tts_provider)
    doc.add("voice", cfg.voice)
    doc.add("bitrate", cfg.bitrate)
    doc.add("max_minutes", cfg.max_minutes)

    gmail = tomlkit.table()
    gmail.add("enabled", cfg.gmail.enabled)
    gmail.add("user", cfg.gmail.user)
    gmail.add("app_password", cfg.gmail.app_password)
    gmail.add("label", cfg.gmail.label)
    gmail.add("method", cfg.gmail.method)
    doc.add("gmail", gmail)

    rss = tomlkit.table()
    rss.add("enabled", cfg.rss.enabled if cfg.rss else False)
    rss.add("feeds", cfg.rss.feeds if cfg.rss and cfg.rss.feeds else [])
    doc.add("rss", rss)

    logging = tomlkit.table()
    logging.add("level", cfg.logging.level)
    logging.add("enable_file_logging", cfg.logging.enable_file_logging)
    if cfg.logging.log_file:
        logging.add("log_file", cfg.logging.log_file)
    doc.add("logging", logging)

    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(tomlkit.dumps(doc), encoding="utf-8")
