from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def load_dotenv(dotenv_path: str | None = None) -> None:
    path = Path(dotenv_path or ".env")
    if not path.exists():
        return
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        os.environ.setdefault(key, value)


@dataclass
class Settings:
    google_oauth_client_secret_file: str | None
    google_oauth_token_file: str | None
    google_service_account_file: str | None
    google_service_account_subject: str | None
    gmail_query: str
    database_url: str | None
    parse_provider: str
    bem_api_key: str | None
    bem_api_url: str | None
    bem_timeout_seconds: int
    bem_function_name: str | None
    bem_workflow_name: str | None
    fathom_api_key: str | None

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            google_oauth_client_secret_file=os.getenv("GOOGLE_OAUTH_CLIENT_SECRET_FILE"),
            google_oauth_token_file=os.getenv("GOOGLE_OAUTH_TOKEN_FILE"),
            google_service_account_file=os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE"),
            google_service_account_subject=os.getenv("GOOGLE_SERVICE_ACCOUNT_SUBJECT"),
            gmail_query=os.getenv("GMAIL_QUERY", 'label:"Investor/Quarterly"'),
            database_url=os.getenv("LPUPDATE_DATABASE_URL"),
            parse_provider=os.getenv("LPUPDATE_PARSE_PROVIDER", "rules"),
            bem_api_key=os.getenv("BEM_API_KEY"),
            bem_api_url=os.getenv("BEM_API_URL"),
            bem_timeout_seconds=int(os.getenv("LPUPDATE_BEM_TIMEOUT_SECONDS", "60")),
            bem_function_name=os.getenv("BEM_FUNCTION_NAME"),
            bem_workflow_name=os.getenv("BEM_WORKFLOW_NAME"),
            fathom_api_key=os.getenv("FATHOM_API_KEY"),
        )
