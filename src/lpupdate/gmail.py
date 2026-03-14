from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse, parse_qs
import json
import os

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.settings.basic",
    "https://www.googleapis.com/auth/gmail.settings.sharing",
]


def build_installed_app_flow(client_secret_file: str):
    flow = InstalledAppFlow.from_client_secrets_file(client_secret_file, SCOPES)
    flow.redirect_uri = "http://localhost"
    return flow


def extract_code_from_redirect_url(value: str) -> str:
    value = value.strip()
    if value.startswith("http://") or value.startswith("https://"):
        parsed = urlparse(value)
        code = parse_qs(parsed.query).get("code", [None])[0]
        if not code:
            raise ValueError("No code= parameter found in redirect URL")
        return code
    return value


@dataclass
class GmailClientConfig:
    client_secret_file: str | None
    token_file: str | None


def get_credentials(cfg: GmailClientConfig):
    creds = None
    token_path = Path(cfg.token_file) if cfg.token_file else None
    client_secret_path = Path(cfg.client_secret_file) if cfg.client_secret_file else None

    if token_path and token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        if token_path:
            token_path.write_text(creds.to_json())

    if not creds or not creds.valid:
        if not client_secret_path or not client_secret_path.exists():
            raise FileNotFoundError(
                "Missing Google OAuth client secret file. Set GOOGLE_OAUTH_CLIENT_SECRET_FILE."
            )
        raise FileNotFoundError(
            "Missing or invalid Gmail token. Run the manual auth flow first to create it."
        )

    return creds


def get_pkce_state_path(token_file: str) -> Path:
    token_path = Path(token_file)
    return token_path.with_name(token_path.name + '.pkce.json')


def build_manual_auth_url(client_secret_file: str, token_file: str):
    flow = build_installed_app_flow(client_secret_file)
    auth_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )
    state_path = get_pkce_state_path(token_file)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps({
        "state": state,
        "code_verifier": getattr(flow, 'code_verifier', None),
        "redirect_uri": flow.redirect_uri,
    }))
    return flow, auth_url, state


def exchange_code_for_token(client_secret_file: str, token_file: str, code_or_url: str):
    os.environ.setdefault("OAUTHLIB_RELAX_TOKEN_SCOPE", "1")
    flow = build_installed_app_flow(client_secret_file)
    state_path = get_pkce_state_path(token_file)
    if not state_path.exists():
        raise FileNotFoundError(
            f"Missing PKCE state file: {state_path}. Run gmail-auth first to generate a fresh auth URL."
        )
    saved = json.loads(state_path.read_text())
    if saved.get("code_verifier"):
        flow.code_verifier = saved["code_verifier"]
    if saved.get("redirect_uri"):
        flow.redirect_uri = saved["redirect_uri"]
    code = extract_code_from_redirect_url(code_or_url)
    flow.fetch_token(code=code)
    creds = flow.credentials
    token_path = Path(token_file)
    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(creds.to_json())
    return creds


def build_gmail_client(cfg: GmailClientConfig):
    creds = get_credentials(cfg)
    return build("gmail", "v1", credentials=creds)
