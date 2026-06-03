"""
gmail_client.py
===============
Gmail API authentication and message sending.

Handles OAuth2 token creation, refresh, and email dispatch.
Place credentials.json in the project root before first run.

First run will open a browser for Google OAuth consent.
Subsequent runs use the cached token.json automatically.
"""

import base64
import logging
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────

# Scope: send-only. Never request broader access than needed.
SCOPES = ["https://www.googleapis.com/auth/gmail.send"]

# Paths — resolve relative to project root (3 levels up from this file)
_ROOT          = Path(__file__).resolve().parent.parent.parent
CREDENTIALS_PATH = _ROOT / "credentials.json"
TOKEN_PATH       = _ROOT / "token.json"


# ── Authentication ────────────────────────────────────────────────────────────

def get_gmail_service():
    """
    Authenticate with the Gmail API and return a service object.

    On first run: opens browser for OAuth consent, saves token.json.
    On subsequent runs: loads and refreshes token.json automatically.

    Returns:
        googleapiclient.discovery.Resource: Authenticated Gmail service.

    Raises:
        FileNotFoundError: If credentials.json is missing.
    """
    if not CREDENTIALS_PATH.exists():
        raise FileNotFoundError(
            f"credentials.json not found at {CREDENTIALS_PATH}.\n"
            "Download it from Google Cloud Console → APIs & Services → Credentials."
        )

    creds = None

    # Load existing token if available
    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)

    # Refresh or re-authenticate
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            logger.info("Refreshing expired Gmail token.")
            creds.refresh(Request())
        else:
            logger.info("Opening browser for Gmail OAuth consent.")
            flow = InstalledAppFlow.from_client_secrets_file(
                str(CREDENTIALS_PATH), SCOPES
            )
            creds = flow.run_local_server(port=0)

        # Save token for next run
        TOKEN_PATH.write_text(creds.to_json(), encoding="utf-8")
        logger.info("Token saved to %s", TOKEN_PATH)

    return build("gmail", "v1", credentials=creds)


# ── Email builder ─────────────────────────────────────────────────────────────

def build_message(
    to: str,
    subject: str,
    html_body: str,
    sender: str = "me",
) -> dict:
    """
    Build a Gmail API message dict from a subject and HTML body.

    Args:
        to:        Recipient email address.
        subject:   Email subject line.
        html_body: HTML content of the email.
        sender:    Sender address — 'me' uses the authenticated account.

    Returns:
        Dict with base64-encoded 'raw' key ready for Gmail API.
    """
    message = MIMEMultipart("alternative")
    message["To"]      = to
    message["From"]    = sender
    message["Subject"] = subject

    # Attach HTML part
    message.attach(MIMEText(html_body, "html", "utf-8"))

    raw = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
    return {"raw": raw}


# ── Send ──────────────────────────────────────────────────────────────────────

def send_email(
    to: str,
    subject: str,
    html_body: str,
) -> bool:
    """
    Send an HTML email via the Gmail API.

    Args:
        to:        Recipient email address.
        subject:   Email subject line.
        html_body: HTML content of the email.

    Returns:
        True if sent successfully, False otherwise.
    """
    try:
        service = get_gmail_service()
        message = build_message(to, subject, html_body)
        sent = service.users().messages().send(
            userId="me", body=message
        ).execute()
        logger.info("Email sent to %s — message id: %s", to, sent.get("id"))
        return True

    except HttpError as e:
        logger.error("Gmail API error sending to %s: %s", to, e)
        return False
    except Exception as e:
        logger.error("Unexpected error sending to %s: %s", to, e)
        return False


def send_bulk(notifications: list[dict]) -> dict:
    """
    Send multiple emails and return a summary.

    Args:
        notifications: List of dicts, each with keys: to, subject, html_body.

    Returns:
        Dict with keys: sent (int), failed (int), failures (list of email addresses).
    """
    results = {"sent": 0, "failed": 0, "failures": []}
    for n in notifications:
        success = send_email(n["to"], n["subject"], n["html_body"])
        if success:
            results["sent"] += 1
        else:
            results["failed"] += 1
            results["failures"].append(n["to"])
    return results
