#!/usr/bin/env python3
"""Check read-only Google OAuth token refreshability without printing secrets."""

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


def check_service(config: dict[str, Any], service: str) -> int:
    try:
        from google.auth.exceptions import RefreshError
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
    except ImportError:
        print(f"WARN: {service} OAuth dependencies are not installed")
        return 0

    if not config.get(f"{service}_enabled", False):
        print(f"PASS: {service} source is disabled")
        return 0

    credentials_path = Path(str(config.get(f"{service}_credentials_path", ""))).expanduser()
    token_path = Path(str(config.get(f"{service}_token_path", ""))).expanduser()
    if not credentials_path.is_file():
        print(f"FAIL: {service} credentials file is missing")
        return 1
    if not token_path.is_file():
        print(f"FAIL: {service} token file is missing")
        return 1

    try:
        credentials = Credentials.from_authorized_user_file(str(token_path), [SCOPES[service]])
    except Exception as exc:
        print(f"FAIL: {service} token could not be loaded: {type(exc).__name__}")
        return 1

    if not credentials.refresh_token:
        print(f"FAIL: {service} token has no refresh token")
        return 1

    try:
        credentials.refresh(Request())
    except RefreshError as exc:
        message = str(exc)
        if "invalid_grant" in message:
            print(f"FAIL: {service} refresh token expired or revoked")
        else:
            print(f"FAIL: {service} token refresh failed: {type(exc).__name__}")
        return 1
    except Exception as exc:
        print(f"FAIL: {service} token refresh failed: {type(exc).__name__}")
        return 1

    token_path.write_text(credentials.to_json(), encoding="utf-8")
    token_path.chmod(0o600)
    print(f"PASS: {service} token refreshed")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Check Google OAuth token health.")
    parser.add_argument("--config", default="/opt/secondbrain/config/secondbrain.local.json")
    parser.add_argument("--service", choices=["gmail", "calendar", "all"], default="all")
    args = parser.parse_args()

    config = load_config(Path(args.config))
    services = ["gmail", "calendar"] if args.service == "all" else [args.service]
    failures = sum(check_service(config, service) for service in services)
    raise SystemExit(1 if failures else 0)


if __name__ == "__main__":
    main()
