# Calendar Read-Only Source

This source adapter lets the daily worker read Google Calendar events for today and tomorrow when explicitly enabled.

This PR does not include credentials and does not enable Calendar by default.

## Safety Model

Calendar access is read-only.

The adapter may:

- read calendar events
- read event metadata
- read event time, title, location, description, and attendees
- query events in a bounded time window
- convert read-only event data into worker source items

The adapter never:

- creates events
- updates events
- deletes events
- patches events
- moves events
- imports events
- uses quick-add
- responds to invitations
- modifies attendees
- changes calendars or ACLs
- writes Calendar credentials or tokens
- gives OpenClaw direct Calendar access

All event content is treated as untrusted source text by the worker prompt.

## Optional Dependencies

Calendar packages are optional and isolated in:

```bash
requirements-calendar.txt
```

Install them only on the machine that will later read Calendar:

```bash
python -m pip install -r requirements-calendar.txt
```

The normal test suite does not require real Calendar packages, credentials, network access, or Google API access.

## Config

Calendar is disabled by default:

```json
{
  "calendar_enabled": false,
  "calendar_credentials_path": "/opt/secondbrain/secrets/calendar_credentials.json",
  "calendar_token_path": "/opt/secondbrain/secrets/calendar_token.json",
  "calendar_ids": ["primary"],
  "calendar_days_ahead": 1,
  "calendar_max_results": 20,
  "calendar_timezone": "America/New_York"
}
```

Only set `calendar_enabled=true` after credentials and a read-only token exist locally on the VPS.

Credential and token files should live outside Git, for example:

```text
/opt/secondbrain/secrets/calendar_credentials.json
/opt/secondbrain/secrets/calendar_token.json
```

The repository `.gitignore` protects common Calendar credential and token filenames.

## Calendar IDs And Window

`calendar_ids` controls which calendars are read. The default is:

```text
primary
```

`calendar_days_ahead=1` means the adapter reads events from the start of today through the end of tomorrow in `calendar_timezone`.

For example, with:

```json
{
  "calendar_days_ahead": 1,
  "calendar_timezone": "America/New_York"
}
```

the query window is bounded to today and tomorrow only.

`calendar_max_results` limits the number of event records fetched.

## Manual Credential Setup Later

When this source is ready to be enabled in a later phase:

1. Create a Google Cloud OAuth client manually.
2. Download the OAuth client JSON to the VPS secrets directory.
3. Generate a user token that grants only:

```text
https://www.googleapis.com/auth/calendar.readonly
```

4. Store the token JSON in the VPS secrets directory.
5. Set `calendar_enabled=true` in the local VPS config.

Do not commit either JSON file.

## Dry-Run Helper

The adapter includes a helper that prints headings only:

```bash
python -m worker.sources.calendar_readonly --config config/secondbrain.local.json --dry-run
```

It prints the count of read Calendar items and headings. It does not print full event bodies and does not write anything.

## Testing

Tests use local fixture events:

```text
tests/fixtures/calendar_readonly_events.json
```

They verify event conversion, project inference, prompt-injection text handling, disabled-by-default behavior, today/tomorrow window calculation, and static absence of Calendar write method calls.

## Troubleshooting

If Calendar is enabled but dependencies are missing, install:

```bash
python -m pip install -r requirements-calendar.txt
```

If credential or token files are missing, the adapter fails clearly before trying to read Calendar.

If the token is invalid or lacks the read-only scope, regenerate the token with only the read-only Calendar scope.

## Next Phase

The next phase is a controlled VPS dry-run with Gmail and Calendar enabled against real read-only sources, still with no generated writes unless explicitly requested through the existing safe worker modes.
