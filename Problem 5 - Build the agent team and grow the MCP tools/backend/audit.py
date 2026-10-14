from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

AUDIT_PATH = Path(__file__).resolve().parents[2] / "output" / "audit_trail.json"


def append_audit_event(
    run_id: str,
    ticket_id: int,
    step: str,
    agent: str,
    status: str,
    tool_names: list[str] | None = None,
) -> None:
    """Persist minimal workflow metadata, never free-form agent or customer content."""
    AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
    if AUDIT_PATH.exists():
        existing = json.loads(AUDIT_PATH.read_text(encoding="utf-8"))
        if not isinstance(existing, list):
            raise ValueError(f"Audit file must contain a JSON array: {AUDIT_PATH}")
    else:
        existing = []

    event: dict[str, Any] = {
        "run_id": run_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "ticket_id": ticket_id,
        "step": step,
        "agent": agent,
        "status": status,
        "tool_names": sorted(set(tool_names or [])),
    }
    existing.append(event)

    temporary_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=AUDIT_PATH.parent,
            prefix=f"{AUDIT_PATH.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary_file:
            temporary_path = temporary_file.name
            json.dump(existing, temporary_file, indent=2, ensure_ascii=False)
            temporary_file.write("\n")
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
        os.replace(temporary_path, AUDIT_PATH)
    finally:
        if temporary_path and os.path.exists(temporary_path):
            os.unlink(temporary_path)
