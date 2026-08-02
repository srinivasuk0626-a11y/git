from __future__ import annotations

import json
from pathlib import Path

from resolveai.domain.models import IdentityRecord, PolicyDocument


def load_policies(data_dir: Path) -> list[PolicyDocument]:
    path = data_dir / "policies.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    return [PolicyDocument.model_validate(item) for item in payload]


def load_identities(data_dir: Path) -> list[IdentityRecord]:
    path = data_dir / "identities.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    return [IdentityRecord.model_validate(item) for item in payload]
