"""
Gmail OAuth authentication and API operations for nl2audio.
"""

from __future__ import annotations

import json
import os
import webbrowser
from pathlib import Path
from typing import List, Optional, Tuple
from urllib.parse import urlparse

import keyring
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from .config import AppConfig
from .logging import get_logger

logger = get_logger(__name__)

# Gmail API scopes
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

# OAuth client secrets file path
CLIENT_SECRETS_FILE = Path.home() / ".nl2audio" / "google_client.json"

# Keyring service and key format
KEYRING_SERVICE = "nl2audio"
KEYRING_KEY_FORMAT = "gmail:{email}"


class GmailOAuthError(Exception):
    """Custom exception for Gmail OAuth errors."""

    pass


def get_credentials_path() -> Path:
    """Get the path to the OAuth client secrets file."""
    return CLIENT_SECRETS_FILE


def check_client_secrets() -> bool:
    """Check if OAuth client secrets file exists."""
    return CLIENT_SECRETS_FILE.exists()


def authenticate_gmail() -> Tuple[str, Credentials]:
    """
    Authenticate with Gmail using OAuth 2.0.

    Returns:
        Tuple of (email, credentials)

    Raises:
        GmailOAuthError: If authentication fails
    """
    if not check_client_secrets():
        raise GmailOAuthError(
            f"OAuth client secrets file not found at {CLIENT_SECRETS_FILE}\n"
            "Please download it from Google Cloud Console and place it in ~/.nl2audio/"
        )

    try:
        # Try to load existing credentials from keyring
        creds = None

        # Check if we have stored credentials
        stored_creds = keyring.get_password(KEYRING_SERVICE, "gmail:temp")
        if stored_creds:
            try:
                creds = Credentials.from_authorized_user_info(
                    json.loads(stored_creds), SCOPES
                )
            except Exception:
                # Invalid stored credentials, remove them
                keyring.delete_password(KEYRING_SERVICE, "gmail:temp")
                creds = None

        # If there are no (valid) credentials available, let the user log in
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                except Exception:
                    # Refresh failed, need to re-authenticate
                    creds = None

            if not creds:
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(CLIENT_SECRETS_FILE), SCOPES
                )

                # Try to open browser for OAuth flow
                try:
                    creds = flow.run_local_server(port=0)
                    logger.info("OAuth authentication completed via browser")
                except Exception as e:
                    logger.warning(
                        f"Browser OAuth failed: {e}, falling back to console"
                    )
                    try:
                        creds = flow.run_console()
                        logger.info("OAuth authentication completed via console")
                    except Exception as e2:
                        raise GmailOAuthError(
                            f"OAuth authentication failed: {e2}\n"
                            "Please check your internet connection and try again."
                        )

        # Get user profile to determine email
        service = build("gmail", "v1", credentials=creds)
        profile = service.users().getProfile(userId="me").execute()
        email = profile["emailAddress"]

        # Store credentials securely
        try:
            keyring.set_password(
                KEYRING_SERVICE, KEYRING_KEY_FORMAT.format(email=email), creds.to_json()
            )
            logger.info(f"Credentials stored securely for {email}")
        except Exception as e:
            logger.warning(f"Could not store credentials in keyring: {e}")
            # Store temporarily for this session
            keyring.set_password(KEYRING_SERVICE, "gmail:temp", creds.to_json())

        return email, creds

    except HttpError as e:
        raise GmailOAuthError(f"Gmail API error: {e}")
    except Exception as e:
        raise GmailOAuthError(f"Authentication failed: {e}")


def get_stored_credentials(email: str) -> Optional[Credentials]:
    """
    Retrieve stored credentials for a specific email.

    Args:
        email: The email address to retrieve credentials for

    Returns:
        Credentials object if found and valid, None otherwise
    """
    try:
        stored_creds = keyring.get_password(
            KEYRING_SERVICE, KEYRING_KEY_FORMAT.format(email=email)
        )
        if stored_creds:
            creds = Credentials.from_authorized_user_info(
                json.loads(stored_creds), SCOPES
            )
            if creds.valid:
                return creds
            elif creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                    # Update stored credentials
                    keyring.set_password(
                        KEYRING_SERVICE,
                        KEYRING_KEY_FORMAT.format(email=email),
                        creds.to_json(),
                    )
                    return creds
                except Exception:
                    # Refresh failed, remove invalid credentials
                    keyring.delete_password(
                        KEYRING_SERVICE, KEYRING_KEY_FORMAT.format(email=email)
                    )
        return None
    except Exception as e:
        logger.warning(f"Error retrieving credentials: {e}")
        return None


def build_gmail_service(creds: Credentials):
    """
    Build Gmail API service from credentials.

    Args:
        creds: Valid OAuth credentials

    Returns:
        Gmail API service object
    """
    return build("gmail", "v1", credentials=creds)


def get_label_id(service, label_name: str) -> Optional[str]:
    """
    Get the ID of a Gmail label by name.

    Args:
        service: Gmail API service
        label_name: Name of the label to find

    Returns:
        Label ID if found, None otherwise
    """
    try:
        results = service.users().labels().list(userId="me").execute()
        labels = results.get("labels", [])

        for label in labels:
            if label["name"] == label_name:
                return label["id"]

        return None
    except HttpError as e:
        logger.error(f"Error getting labels: {e}")
        return None


def list_messages(service, label_id: str, max_results: int = 5) -> List[dict]:
    """
    List messages from a specific label.

    Args:
        service: Gmail API service
        label_id: ID of the label to search
        max_results: Maximum number of messages to return

    Returns:
        List of message objects
    """
    try:
        results = (
            service.users()
            .messages()
            .list(userId="me", labelIds=[label_id], maxResults=max_results)
            .execute()
        )

        messages = results.get("messages", [])
        if not messages:
            return []

        # Get full message details
        full_messages = []
        for msg in messages:
            try:
                full_msg = (
                    service.users()
                    .messages()
                    .get(userId="me", id=msg["id"], format="full")
                    .execute()
                )
                full_messages.append(full_msg)
            except HttpError as e:
                logger.warning(f"Could not get message {msg['id']}: {e}")
                continue

        return full_messages

    except HttpError as e:
        logger.error(f"Error listing messages: {e}")
        return []


def extract_message_subject(message: dict) -> str:
    """
    Extract subject from a Gmail message.

    Args:
        message: Gmail message object

    Returns:
        Subject string
    """
    headers = message.get("payload", {}).get("headers", [])
    for header in headers:
        if header["name"].lower() == "subject":
            return header["value"]
    return "No Subject"


def extract_message_content(message: dict) -> Tuple[str, str]:
    """
    Extract HTML and text content from a Gmail message.

    Args:
        message: Gmail message object

    Returns:
        Tuple of (html_content, text_content)
    """

    def extract_part_content(part):
        if part.get("mimeType") == "text/html":
            return part.get("body", {}).get("data", ""), ""
        elif part.get("mimeType") == "text/plain":
            return "", part.get("body", {}).get("data", "")
        elif "parts" in part:
            html_content, text_content = "", ""
            for subpart in part["parts"]:
                sub_html, sub_text = extract_part_content(subpart)
                html_content += sub_html
                text_content += sub_text
            return html_content, text_content
        return "", ""

    payload = message.get("payload", {})
    html_content, text_content = extract_part_content(payload)

    # Decode base64 content
    import base64

    if html_content:
        try:
            html_content = base64.urlsafe_b64decode(html_content).decode("utf-8")
        except Exception:
            html_content = ""

    if text_content:
        try:
            text_content = base64.urlsafe_b64decode(text_content).decode("utf-8")
        except Exception:
            text_content = ""

    return html_content, text_content
