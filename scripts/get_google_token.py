#!/usr/bin/env python3
"""One-time helper to mint a Google OAuth refresh token for Calendar access.

Prerequisites:
  1. In Google Cloud Console, enable the "Google Calendar API".
  2. Create an OAuth 2.0 Client ID of type "Desktop app".
  3. Export the client credentials before running:
       export GOOGLE_CLIENT_ID=...
       export GOOGLE_CLIENT_SECRET=...

Run:
    python scripts/get_google_token.py

It opens a browser for consent, then prints the refresh token. Copy it into
your .env (GOOGLE_REFRESH_TOKEN) or a GitHub Actions secret.
"""
from __future__ import annotations

import os
import sys

SCOPES = ["https://www.googleapis.com/auth/calendar.events"]


def main() -> int:
    client_id = os.getenv("GOOGLE_CLIENT_ID")
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
    if not (client_id and client_secret):
        print("ERROR: set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET env vars first.")
        return 1

    from google_auth_oauthlib.flow import InstalledAppFlow

    client_config = {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost"],
        }
    }
    flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
    creds = flow.run_local_server(port=0, prompt="consent")

    print("\n=== SUCCESS ===")
    print("GOOGLE_REFRESH_TOKEN=" + (creds.refresh_token or "<none returned>"))
    print("\nAdd this to your .env or GitHub Actions secrets.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
