from __future__ import annotations

import re
from dataclasses import dataclass, field
from hashlib import sha256
from typing import Iterable


INJECTION_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(pattern, re.IGNORECASE | re.MULTILINE)
    for pattern in (
        r"ignore\s+(all|any|the)?\s*(previous|prior|system)\s+instructions",
        r"reveal\s+(the\s+)?(system|developer)\s+prompt",
        r"print\s+(all\s+)?secrets?",
        r"bypass\s+(security|approval|authorization)",
        r"execute\s+(this\s+)?(shell|bash|powershell|sql)",
        r"<script\b",
        r"BEGIN\s+(SYSTEM|DEVELOPER)\s+PROMPT",
        r"curl\s+https?://",
    )
)

SECRET_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\bAKIA[0-9A-Z]{16}\b",
        r"\bsk-[A-Za-z0-9_-]{20,}\b",
        r"-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----",
        r"\b(password|passwd|secret)\s*[:=]\s*\S+",
    )
)


@dataclass(slots=True)
class GuardrailFinding:
    blocked: bool
    reasons: list[str] = field(default_factory=list)
    fingerprint: str = ""


def _matches(text: str, patterns: Iterable[re.Pattern[str]]) -> list[str]:
    return sorted({pattern.pattern for pattern in patterns if pattern.search(text)})


def inspect_untrusted_text(text: str, *, block_on_injection: bool = True) -> GuardrailFinding:
    injection_matches = _matches(text, INJECTION_PATTERNS)
    secret_matches = _matches(text, SECRET_PATTERNS)
    reasons: list[str] = []
    if injection_matches:
        reasons.append("prompt_injection_pattern")
    if secret_matches:
        reasons.append("possible_secret_exposure")
    return GuardrailFinding(
        blocked=(bool(injection_matches) and block_on_injection) or bool(secret_matches),
        reasons=reasons,
        fingerprint=sha256(text.encode("utf-8")).hexdigest()[:16],
    )


def authorize_action(*, action: str, risk_flags: list[str], employment_status: str) -> GuardrailFinding:
    reasons: list[str] = []
    blocked = False
    if employment_status != "active":
        blocked = True
        reasons.append("requester_not_active")
    if "identity_under_review" in risk_flags and action in {"grant_access", "restore_access"}:
        blocked = True
        reasons.append("identity_under_review")
    if action in {"grant_admin", "disable_audit", "export_secrets"}:
        blocked = True
        reasons.append("action_not_allowlisted")
    return GuardrailFinding(blocked=blocked, reasons=reasons)
