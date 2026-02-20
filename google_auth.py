"""
Google OAuth2 helper with token persistence.
Token is saved to ~/cred/google_token.json and reused/refreshed automatically.

Usage:
    from google_auth import get_credentials
    creds = get_credentials(['https://www.googleapis.com/auth/calendar.readonly'])
"""

import os
from pathlib import Path
from dotenv import load_dotenv
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow

load_dotenv(Path("~/life/.env").expanduser())

CLIENT_SECRET_FILE = os.environ.get(
    "GOOGLE_CLIENT_SECRET_FILE",
    str(Path("~/cred/google_oauth_client.json").expanduser())
)
TOKEN_FILE = str(Path("~/cred/google_token.json").expanduser())


def get_credentials(scopes: list[str]) -> Credentials:
    """
    Return valid Google credentials, refreshing or re-authorizing as needed.
    Browser flow only runs on first call or if token is revoked.
    """
    creds = None

    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, scopes)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            print("✓ Token refreshed silently")
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET_FILE, scopes)
            creds = flow.run_local_server(port=0)
            print("✓ OAuth flow completed")

        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())
        print(f"✓ Token saved to {TOKEN_FILE}")

    return creds
