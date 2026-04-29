"""Email digest delivery via Resend."""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass

RESEND_ENDPOINT = "https://api.resend.com/emails"


@dataclass
class EmailConfig:
    api_key: str
    from_addr: str
    to_addrs: tuple[str, ...]
    subject_prefix: str = "[DBI Land]"

    @classmethod
    def from_env(cls, prefix: str = "DBI_RESEND_") -> "EmailConfig":
        return cls(
            api_key=os.environ[f"{prefix}API_KEY"],
            from_addr=os.environ[f"{prefix}FROM"],
            to_addrs=tuple(
                a.strip() for a in os.environ[f"{prefix}TO"].split(",") if a.strip()
            ),
            subject_prefix=os.environ.get(f"{prefix}SUBJECT_PREFIX", "[DBI Land]"),
        )


def send_digest(
    config: EmailConfig,
    *,
    subject: str,
    html: str,
    dry_run: bool = False,
) -> dict:
    payload = {
        "from": config.from_addr,
        "to": list(config.to_addrs),
        "subject": f"{config.subject_prefix} {subject}".strip(),
        "html": html,
    }
    if dry_run:
        return {"dry_run": True, "payload": payload}
    req = urllib.request.Request(
        RESEND_ENDPOINT,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {config.api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8")
            return {"status": resp.status, "body": json.loads(body) if body else {}}
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Resend HTTP {e.code}: {body}") from e
