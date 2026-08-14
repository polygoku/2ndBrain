#!/usr/bin/env python3
"""Reauthorize read-only Google OAuth tokens for the VPS worker.

This helper intentionally prints only metadata and the Google consent URL. It
does not print credential JSON, token JSON, refresh tokens, or access tokens.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SCOPES = {
    "gmail": "https://www.googleapis.com/auth/gmail.readonly",
    "calendar": "https://www.googleapis.com/auth/calendar.readonly",
}


def load_config(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise SystemExit("FAIL: Config JSON must be an object")
    return data


def config_paths(config: dict[str, Any], service: str) -> tuple[Path, Path]:
    credentials_key = f"{service}_credentials_path"
    token_key = f"{service}_token_path"
    try:
        credentials_path = Path(str(config[credentials_key])).expanduser()
        token_path = Path(str(config[token_key])).expanduser()
    except KeyError as exc:
        raise SystemExit(f"FAIL: Missing config key: {exc.args[0]}") from exc
    if not credentials_path.is_file():
        raise SystemExit(f"FAIL: {service} credentials file is missing: {credentials_path}")
    token_path.parent.mkdir(parents=True, exist_ok=True)
    return credentials_path, token_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Refresh a read-only Gmail or Calendar OAuth token without printing secrets."
    )
    parser.add_argument("--config", default="/opt/secondbrain/config/secondbrain.local.json")
    parser.add_argument("--service", choices=sorted(SCOPES), required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8766)
    args = parser.parse_args()

    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError as exc:
        raise SystemExit(
            "FAIL: google-auth-oauthlib is required. Install requirements-gmail.txt "
            "or requirements-calendar.txt on the VPS."
        ) from exc

    config = load_config(Path(args.config))
    credentials_path, token_path = config_paths(config, args.service)
    scope = SCOPES[args.service]

    flow = InstalledAppFlow.from_client_secrets_file(str(credentials_path), scopes=[scope])
    credentials = flow.run_local_server(
        host=args.host,
        port=args.port,
        authorization_prompt_message="AUTH_URL: {url}",
        success_message=(
            f"{args.service.title()} read-only authorization completed. "
            "You can close this browser tab."
        ),
        open_browser=False,
        access_type="offline",
        prompt="consent",
    )
    token_path.write_text(credentials.to_json(), encoding="utf-8")
    token_path.chmod(0o600)
    print(f"PASS: {args.service} token replaced")
    print(f"Scope: {scope}")
    print(f"Token path: {token_path}")


if __name__ == "__main__":
    main()
