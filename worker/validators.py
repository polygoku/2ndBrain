"""Conservative validation for generated markdown."""

from __future__ import annotations

from dataclasses import dataclass


PRIMARY_SHELL_PREFIXES = (
    "rm ",
    "mv ",
    "cp ",
    "sudo ",
    "curl ",
    "wget ",
    "bash ",
    "sh ",
    "powershell ",
    "python ",
    "python3 ",
)

FORBIDDEN_PHRASES = (
    "delete the file",
    "delete files",
    "remove the file",
    "move the file",
    "move files",
    "expose credential",
    "expose credentials",
    "print credential",
    "print credentials",
    "send email",
    "email has been sent",
)


@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    error: str = ""


def validate_markdown(content: str) -> ValidationResult:
    stripped = content.strip()
    if not stripped:
        return ValidationResult(False, "Generated output is empty")

    if not any(marker in stripped for marker in ("# ", "## ", "- ", "|")):
        return ValidationResult(False, "Generated output does not look like markdown")

    first_line = next((line.strip().lower() for line in stripped.splitlines() if line.strip()), "")
    if first_line.startswith(PRIMARY_SHELL_PREFIXES):
        return ValidationResult(False, "Generated output appears to be a shell command")

    lowered = stripped.lower()
    for phrase in FORBIDDEN_PHRASES:
        if phrase in lowered:
            return ValidationResult(False, f"Generated output contains forbidden request: {phrase}")

    return ValidationResult(True)

