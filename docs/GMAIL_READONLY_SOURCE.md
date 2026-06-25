# Gmail Read-Only Source

This source adapter lets the daily worker read Gmail message metadata and plain-text message snippets later, when explicitly enabled.

This PR does not include credentials and does not enable Gmail by default.

## Safety Model

Gmail access is read-only.

The adapter may:

- read message metadata
- read message snippets or plain-text message body content
- read labels attached to returned messages
- search/list messages using the configured query and labels
- convert read-only email data into worker source items

The adapter never:

- sends email
- creates drafts
- replies or forwards
- deletes, trashes, archives, stars, or marks messages
- changes labels
- downloads attachments
- writes Gmail credentials or tokens
- gives OpenClaw direct Gmail access

All email content is treated as untrusted source text by the worker prompt.

## Optional Dependencies

Gmail packages are optional and isolated in:

```bash
requirements-gmail.txt
```

Install them only on the machine that will later read Gmail:

```bash
python -m pip install -r requirements-gmail.txt
```

The normal test suite does not require real Gmail packages, credentials, network access, or Google API access.

## Config

Gmail is disabled by default:

```json
{
  "gmail_enabled": false,
  "gmail_credentials_path": "/opt/secondbrain/secrets/gmail_credentials.json",
  "gmail_token_path": "/opt/secondbrain/secrets/gmail_token.json",
  "gmail_labels": ["INBOX", "Action", "Waiting"],
  "gmail_max_results": 10,
  "gmail_query": "newer_than:14d"
}
```

Only set `gmail_enabled=true` after credentials and a read-only token exist locally on the VPS.

Credential and token files should live outside Git, for example:

```text
/opt/secondbrain/secrets/gmail_credentials.json
/opt/secondbrain/secrets/gmail_token.json
```

The repository `.gitignore` protects common credential and token filenames.

## Query And Labels

`gmail_query` is passed to Gmail search. The default reads recent messages:

```text
newer_than:14d
```

`gmail_labels` limits results to the configured label IDs or names, such as:

```text
INBOX
Action
Waiting
```

`gmail_max_results` limits the number of message records fetched.

## Manual Credential Setup Later

When this source is ready to be enabled in a later phase:

1. Create a Google Cloud OAuth client manually.
2. Download the OAuth client JSON to the VPS secrets directory.
3. Generate a user token that grants only:

```text
https://www.googleapis.com/auth/gmail.readonly
```

4. Store the token JSON in the VPS secrets directory.
5. Set `gmail_enabled=true` in the local VPS config.

Do not commit either JSON file.

## Dry-Run Helper

The adapter includes a helper that prints headings only:

```bash
python -m worker.sources.gmail_readonly --config config/secondbrain.local.json --dry-run
```

It prints the count of read Gmail items and headings. It does not print full email bodies and does not write anything.

## Testing

Tests use local fixture messages:

```text
tests/fixtures/gmail_readonly_messages.json
```

They verify message conversion, project inference, prompt-injection text handling, disabled-by-default behavior, and static absence of Gmail write method calls.

## Troubleshooting

If Gmail is enabled but dependencies are missing, install:

```bash
python -m pip install -r requirements-gmail.txt
```

If credential or token files are missing, the adapter fails clearly before trying to read Gmail.

If the token is invalid or lacks the read-only scope, regenerate the token with only the read-only Gmail scope.

## Next Phase

The next source-adapter phase is Calendar read-only support. Calendar should follow the same pattern: disabled by default, read-only scope only, no credentials in Git, and tests that do not require live Google access.
