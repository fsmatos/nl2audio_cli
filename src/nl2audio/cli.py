from __future__ import annotations
from pathlib import Path
import typer, sys, io, os, http.server, socketserver, threading
from rich.console import Console
from rich.panel import Panel
from .config import ensure_config, save_config, AppConfig, CONFIG_PATH
from .store import DB
from .ingest import from_source
from .tts import synthesize, TTSLengthError
from .feed import build_feed
from .ingest_email import fetch_gmail
from .gmail_oauth import authenticate_gmail, get_stored_credentials, build_gmail_service, get_label_id, list_messages, extract_message_subject, GmailOAuthError
from pydub import AudioSegment
from .validation import validate_config_health, check_output_directory, check_gmail_credentials, ValidationError
from .validators import validate_config, validate_runtime, get_check_summary, CheckResult
from .logging import setup_logging, get_logger, log_success, log_error, log_info, log_warning

app = typer.Typer(help="Turn newsletters into a private podcast.")

console = Console()

# Global debug flag
DEBUG_MODE = False

def _init_logging(cfg: AppConfig) -> None:
    """Initialize logging based on configuration."""
    global DEBUG_MODE
    
    # Override log level if debug mode is enabled
    log_level = "DEBUG" if DEBUG_MODE else cfg.logging.level
    
    log_file = None
    if cfg.logging.enable_file_logging:
        if cfg.logging.log_file:
            log_file = Path(cfg.logging.log_file).expanduser()
        else:
            # Default log file location
            log_file = cfg.output_dir / "nl2audio.log"
    
    setup_logging(
        log_file=log_file,
        level=log_level,
        enable_rich=True
    )
    
    if DEBUG_MODE:
        logger = get_logger()
        logger.info("🐛 Debug mode enabled - verbose logging active")

@app.callback()
def main(debug: bool = typer.Option(False, "--debug", "-d", help="Enable debug mode with verbose logging")):
    """Turn newsletters into a private podcast."""
    global DEBUG_MODE
    DEBUG_MODE = debug

@app.command()
def init():
    """Create a default config file at ~/.nl2audio/config.toml"""
    cfg = ensure_config()
    save_config(cfg)
    console.print(Panel.fit(f"Config written to [bold]{CONFIG_PATH}[/bold]"))
    
    # Initialize logging after config is created
    _init_logging(cfg)
    log_success(f"Configuration initialized at {CONFIG_PATH}")



@app.command()
def doctor(
    probe_openai: bool = typer.Option(False, "--probe-openai", help="Test OpenAI API connectivity"),
    probe_gmail: bool = typer.Option(False, "--probe-gmail", help="Test Gmail connectivity")
):
    """Run comprehensive health checks and show detailed report."""
    try:
        cfg = ensure_config()
        
        # Initialize logging
        _init_logging(cfg)
        logger = get_logger()
        
        logger.info("🏥 Running comprehensive health checks...")
        console.print("🏥 Running comprehensive health checks...")
        
        # Run validations
        results = validate_runtime(cfg, check_openai=probe_openai, check_gmail=probe_gmail)
        summary = get_check_summary(results)
        
        # Display results in a table
        from rich.table import Table
        from rich.text import Text
        
        table = Table(title="Health Check Results")
        table.add_column("Check", style="cyan", no_wrap=True)
        table.add_column("Status", style="bold")
        table.add_column("Message", style="white")
        table.add_column("Remediation", style="yellow")
        
        for result in results:
            # Color the status
            status_style = {
                "pass": "green",
                "warn": "yellow", 
                "fail": "red"
            }[result.status]
            
            status_text = Text(result.status.upper(), style=status_style)
            
            # Add to table
            table.add_row(
                result.name,
                status_text,
                result.message,
                result.remediation or "N/A"
            )
        
        console.print(table)
        
        # Display summary
        summary_text = Text()
        if summary["failed"] > 0:
            summary_text.append(f"❌ {summary['failed']} checks failed", style="red")
            if summary["warnings"] > 0:
                summary_text.append(f", ⚠️ {summary['warnings']} warnings", style="yellow")
            summary_text.append(f", ✅ {summary['passed']} passed", style="green")
            exit_code = 2
        elif summary["warnings"] > 0:
            summary_text.append(f"⚠️ {summary['warnings']} warnings", style="yellow")
            summary_text.append(f", ✅ {summary['passed']} passed", style="green")
            exit_code = 1
        else:
            summary_text.append(f"✅ All {summary['passed']} checks passed!", style="green")
            exit_code = 0
        
        console.print(f"\n{summary_text}")
        
        # Exit with appropriate code
        if exit_code != 0:
            raise typer.Exit(code=exit_code)
            
    except Exception as e:
        log_error(f"Health check failed: {e}")
        console.print(f"❌ Health check failed: {e}")
        raise typer.Exit(code=1)

def _ensure_dirs(cfg: AppConfig):
    cfg.output_dir.mkdir(parents=True, exist_ok=True)
    (cfg.output_dir / "episodes").mkdir(exist_ok=True)

def _db_path(cfg: AppConfig) -> Path:
    return cfg.output_dir / "db.sqlite"

@app.command()
def add(source: str = typer.Option(..., "--source", "-s", help="File path, URL, or '-' for stdin"),
        title: str = typer.Option(None, "--title", "-t", help="Episode title (optional)")):
    """Add an episode from a source (file, URL, or stdin)."""
    try:
        cfg = ensure_config()
        
        # Initialize logging
        _init_logging(cfg)
        logger = get_logger()
        
        logger.info(f"Adding episode from source: {source}")
        
        # Quick validation before proceeding
        validation_results = validate_config(cfg)
        failed_checks = [r for r in validation_results if r.status == "fail"]
        if failed_checks:
            error_msg = f"Configuration validation failed:\n" + "\n".join([f"• {r.name}: {r.message}" for r in failed_checks])
            log_error(error_msg)
            console.print(f"[red]Configuration Error:[/red] {error_msg}")
            raise typer.Exit(code=1)
        
        # Validate configuration values
        if not cfg.voice or not cfg.voice.strip():
            error_msg = "Voice configuration is empty or invalid"
            log_error(error_msg)
            console.print(f"[red]Configuration Error:[/red] {error_msg}")
            raise typer.Exit(code=1)
        
        if cfg.max_minutes <= 0:
            error_msg = f"max_minutes must be positive, got: {cfg.max_minutes}"
            log_error(error_msg)
            console.print(f"[red]Configuration Error:[/red] {error_msg}")
            raise typer.Exit(code=1)
        
        # Validate bitrate format
        valid_bitrates = ["32k", "64k", "96k", "128k", "192k", "256k", "320k"]
        if cfg.bitrate not in valid_bitrates:
            error_msg = f"Invalid bitrate '{cfg.bitrate}'. Valid options: {', '.join(valid_bitrates)}"
            log_error(error_msg)
            console.print(f"[red]Configuration Error:[/red] {error_msg}")
            raise typer.Exit(code=1)
        
        # Validate configuration values
        if not cfg.voice or not cfg.voice.strip():
            error_msg = "Voice configuration is empty or invalid"
            log_error(error_msg)
            console.print(f"[red]Configuration Error:[/red] {error_msg}")
            raise typer.Exit(code=1)
        
        if cfg.max_minutes <= 0:
            error_msg = f"max_minutes must be positive, got: {cfg.max_minutes}"
            log_error(error_msg)
            console.print(f"[red]Configuration Error:[/red] {error_msg}")
            raise typer.Exit(code=1)
        
        # Validate bitrate format
        valid_bitrates = ["32k", "64k", "96k", "128k", "192k", "256k", "320k"]
        if cfg.bitrate not in valid_bitrates:
            error_msg = f"Invalid bitrate '{cfg.bitrate}'. Valid options: {', '.join(valid_bitrates)}"
            log_error(error_msg)
            console.print(f"[red]Configuration Error:[/red] {error_msg}")
            raise typer.Exit(code=1)
        
        _ensure_dirs(cfg)
        
        stdin_text = None
        if source.strip() == "-":
            stdin_text = sys.stdin.read()
            logger.info("Reading content from stdin")

        res = from_source(source, stdin_text)
        ep_title = title or res.title or "Untitled"
        mp3_path = cfg.output_dir / "episodes" / f"{ep_title.replace(' ', '_')}.mp3"
        
        logger.info(f"Processing episode: {ep_title}")

        try:
            content_bytes = synthesize(res.text, cfg.voice, mp3_path, bitrate=cfg.bitrate, max_minutes=cfg.max_minutes)
            logger.info(f"TTS completed successfully for: {ep_title}")
        except TTSLengthError as e:
            log_error(f"TTS length error: {e}")
            console.print(f"[red]Error:[/red] {e}")
            raise typer.Exit(code=1)
        except ValidationError as e:
            log_error(f"TTS validation error: {e}")
            console.print(f"[red]Validation Error:[/red] {e}")
            raise typer.Exit(code=1)
        except Exception as e:
            log_error(f"TTS failed: {e}")
            console.print(f"[red]TTS failed:[/red] {e}")
            raise typer.Exit(code=1)

        # Duration naive approximation by file size (or could parse via pydub)
        try:
            duration_sec = int(len(AudioSegment.from_file(mp3_path, format="mp3")) / 1000)
            logger.debug(f"Audio duration: {duration_sec} seconds")
        except Exception as e:
            logger.warning(f"Could not determine audio duration: {e}")
            duration_sec = 0

        # Use context manager for database operations
        with DB(_db_path(cfg)) as db:
            db.add_episode(ep_title, res.source, mp3_path, duration_sec, content_bytes)
        
        log_success(f"Episode added successfully: {ep_title}")
        console.print(Panel.fit(f"Added episode: [bold]{ep_title}[/bold]\nFile: {mp3_path}"))
        
    except ValidationError as e:
        log_error(f"Configuration error: {e}")
        console.print(f"[red]Configuration Error:[/red] {e}")
        raise typer.Exit(code=1)
    except Exception as e:
        log_error(f"Unexpected error: {e}")
        console.print(f"[red]Unexpected Error:[/red] {e}")
        raise typer.Exit(code=1)

@app.command("gen-feed")
def gen_feed():
    """Generate feed.xml from the episodes in the database."""
    try:
        cfg = ensure_config()
        
        # Initialize logging
        _init_logging(cfg)
        logger = get_logger()
        
        logger.info("Generating RSS feed")
        
        # Quick validation before proceeding
        validation_results = validate_config(cfg)
        failed_checks = [r for r in validation_results if r.status == "fail"]
        if failed_checks:
            error_msg = f"Configuration validation failed:\n" + "\n".join([f"• {r.name}: {r.message}" for r in failed_checks])
            log_error(error_msg)
            console.print(f"[red]Configuration Error:[/red] {error_msg}")
            raise typer.Exit(code=1)
        
        _ensure_dirs(cfg)
        
        # Use context manager for database operations
        with DB(_db_path(cfg)) as db:
            episodes = db.list_episodes()
            logger.info(f"Found {len(episodes)} episodes in database")
            
            xml_path = build_feed(cfg.output_dir, cfg.feed_title, cfg.site_url, episodes)
        
        log_success(f"RSS feed generated successfully: {xml_path}")
        console.print(Panel.fit(f"Feed generated: [bold]{xml_path}[/bold]"))
        
    except Exception as e:
        log_error(f"Feed generation failed: {e}")
        console.print(f"[red]Feed generation failed:[/red] {e}")
        raise typer.Exit(code=1)

@app.command()
def serve(port: int = typer.Option(8080, help="Port to serve feed & episodes", min=1, max=65535)):
    """Serve output directory over HTTP (for local podcast subscription)."""
    try:
        cfg = ensure_config()
        
        # Initialize logging
        _init_logging(cfg)
        logger = get_logger()
        
        logger.info(f"Starting HTTP server on port {port}")
        
        # Quick validation before proceeding
        validation_results = validate_config(cfg)
        failed_checks = [r for r in validation_results if r.status == "fail"]
        if failed_checks:
            error_msg = f"Configuration validation failed:\n" + "\n".join([f"• {r.name}: {r.message}" for r in failed_checks])
            log_error(error_msg)
            console.print(f"[red]Configuration Error:[/red] {error_msg}")
            raise typer.Exit(code=1)
        
        _ensure_dirs(cfg)
        os.chdir(cfg.output_dir)

        handler = http.server.SimpleHTTPRequestHandler
        with socketserver.TCPServer(("0.0.0.0", port), handler) as httpd:
            log_success(f"HTTP server started on port {port}")
            console.print(Panel.fit(f"Serving {cfg.output_dir} at http://127.0.0.1:{port}"))
            try:
                httpd.serve_forever()
            except KeyboardInterrupt:
                logger.info("HTTP server stopped by user")
                pass
    except Exception as e:
        log_error(f"Server failed to start: {e}")
        console.print(f"[red]Server failed to start:[/red] {e}")
        raise typer.Exit(code=1)

@app.command("fetch-email")
def fetch_email():
    """Fetch new emails from Gmail and convert them to episodes."""
    try:
        cfg = ensure_config()
        if not cfg.gmail.enabled:
            log_error("Gmail fetching is disabled in config")
            console.print("[red]Gmail fetching is disabled in config.[/red]")
            raise typer.Exit(1)

        # Initialize logging
        _init_logging(cfg)
        logger = get_logger()
        
        logger.info("Starting Gmail email fetch")
        
        # Quick validation before proceeding
        validation_results = validate_config(cfg)
        failed_checks = [r for r in validation_results if r.status == "fail"]
        if failed_checks:
            error_msg = f"Configuration validation failed:\n" + "\n".join([f"• {r.name}: {r.message}" for r in failed_checks])
            log_error(error_msg)
            console.print(f"[red]Configuration Error:[/red] {error_msg}")
            raise typer.Exit(code=1)

        _ensure_dirs(cfg)
        
        messages = fetch_gmail(cfg.gmail)
        if not messages:
            logger.info("No new emails found")
            console.print("No new emails found.")
            return

        logger.info(f"Found {len(messages)} emails to process")
        
        # Use context manager for database operations
        with DB(_db_path(cfg)) as db:
            for i, msg in enumerate(messages, 1):
                try:
                    logger.info(f"Processing email {i}/{len(messages)}: {msg.title}")
                    ep_title = msg.title
                    mp3_path = cfg.output_dir / "episodes" / f"{ep_title.replace(' ', '_')}.mp3"
                    
                    content_bytes = synthesize(msg.text, cfg.voice, mp3_path, bitrate=cfg.bitrate, max_minutes=cfg.max_minutes)
                    duration_sec = int(len(AudioSegment.from_file(mp3_path, format="mp3")) / 1000)
                    
                    db.add_episode(ep_title, msg.source, mp3_path, duration_sec, content_bytes)
                    log_success(f"Email processed successfully: {ep_title}")
                    console.print(f"[green]Added episode from email:[/green] {ep_title}")
                    
                except Exception as e:
                    log_error(f"Failed to process email '{msg.title}': {e}")
                    console.print(f"[red]Failed to process email '{msg.title}':[/red] {e}")
                    continue
                
    except ValidationError as e:
        log_error(f"Configuration error: {e}")
        console.print(f"[red]Configuration Error:[/red] {e}")
        raise typer.Exit(code=1)
    except Exception as e:
        log_error(f"Email fetching failed: {e}")
        console.print(f"[red]Email fetching failed:[/red] {e}")
        raise typer.Exit(code=1)

@app.command("connect-gmail")
def connect_gmail():
    """Connect to Gmail using OAuth 2.0 authentication."""
    try:
        cfg = ensure_config()
        
        # Initialize logging
        _init_logging(cfg)
        logger = get_logger()
        
        logger.info("Starting Gmail OAuth authentication")
        console.print("🔐 Starting Gmail OAuth authentication...")
        
        # Authenticate with Gmail
        email, creds = authenticate_gmail()
        
        # Update configuration
        cfg.gmail.enabled = True
        cfg.gmail.user = email
        cfg.gmail.method = "oauth"
        cfg.gmail.app_password = ""  # Clear app password when using OAuth
        
        # Save updated configuration
        save_config(cfg)
        
        log_success(f"Gmail OAuth authentication completed for {email}")
        console.print(Panel.fit(
            f"✅ Gmail OAuth authentication successful!\n\n"
            f"Email: [bold]{email}[/bold]\n"
            f"Method: [bold]OAuth[/bold]\n"
            f"Configuration updated and saved.\n\n"
            f"You can now use 'nl2audio fetch-email' to fetch emails via OAuth.",
            style="green"
        ))
        
    except GmailOAuthError as e:
        log_error(f"Gmail OAuth authentication failed: {e}")
        console.print(f"[red]❌ Gmail OAuth authentication failed:[/red]\n{e}")
        raise typer.Exit(code=1)
    except Exception as e:
        log_error(f"Unexpected error during Gmail OAuth: {e}")
        console.print(f"[red]❌ Unexpected error:[/red] {e}")
        raise typer.Exit(code=1)

@app.command("gmail-test")
def gmail_test():
    """Test Gmail OAuth connection and list up to 5 messages from 'Newsletters' label."""
    try:
        cfg = ensure_config()
        if not cfg.gmail.enabled:
            log_error("Gmail is disabled in config")
            console.print("[red]Gmail is disabled in config.[/red]")
            raise typer.Exit(1)
        
        if cfg.gmail.method != "oauth":
            log_error("Gmail OAuth is not configured")
            console.print("[red]Gmail OAuth is not configured. Run 'nl2audio connect-gmail' first.[/red]")
            raise typer.Exit(1)
        
        # Initialize logging
        _init_logging(cfg)
        logger = get_logger()
        
        logger.info("Testing Gmail OAuth connection")
        console.print("🧪 Testing Gmail OAuth connection...")
        
        # Get stored credentials
        creds = get_stored_credentials(cfg.gmail.user)
        if not creds:
            log_error("No valid OAuth credentials found")
            console.print("[red]No valid OAuth credentials found. Run 'nl2audio connect-gmail' first.[/red]")
            raise typer.Exit(1)
        
        # Build Gmail service
        service = build_gmail_service(creds)
        console.print("✅ Successfully connected to Gmail via OAuth")
        
        # Get label ID
        label_id = get_label_id(service, cfg.gmail.label)
        if not label_id:
            console.print(f"❌ Label '{cfg.gmail.label}' not found")
            # List available labels
            try:
                labels_result = service.users().labels().list(userId='me').execute()
                labels = labels_result.get('labels', [])
                console.print(f"📁 Available labels: {[label['name'] for label in labels[:10]]}")
                if len(labels) > 10:
                    console.print(f"   ... and {len(labels) - 10} more")
            except Exception as e:
                console.print(f"⚠️  Could not list labels: {e}")
            return
        
        # List messages
        messages = list_messages(service, label_id, max_results=5)
        console.print(f"📧 Found {len(messages)} messages in label '{cfg.gmail.label}'")
        
        if messages:
            console.print("\n📋 Message subjects:")
            for i, msg in enumerate(messages, 1):
                subject = extract_message_subject(msg)
                console.print(f"  {i}. {subject}")
        else:
            console.print("❌ No messages found with this label!")
        
        console.print("\n✅ Gmail OAuth test completed successfully!")
        
    except GmailOAuthError as e:
        log_error(f"Gmail OAuth test failed: {e}")
        console.print(f"[red]❌ Gmail OAuth test failed:[/red] {e}")
        raise typer.Exit(code=1)
    except Exception as e:
        log_error(f"Unexpected error during Gmail OAuth test: {e}")
        console.print(f"[red]❌ Unexpected error:[/red] {e}")
        raise typer.Exit(code=1)

@app.command()
def quickstart():
    """Display the quickstart guide."""
    try:
        # Get the path to the QUICKSTART.md file
        quickstart_path = Path(__file__).parent.parent.parent / "QUICKSTART.md"
        
        if not quickstart_path.exists():
            console.print("[red]Error: QUICKSTART.md not found[/red]")
            raise typer.Exit(code=1)
        
        # Read and display the content
        with open(quickstart_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        console.print(Panel.fit(content, title="📚 nl2audio Quickstart Guide", border_style="blue"))
        
    except Exception as e:
        log_error(f"Failed to display quickstart guide: {e}")
        console.print(f"[red]Error displaying quickstart guide:[/red] {e}")
        raise typer.Exit(code=1)