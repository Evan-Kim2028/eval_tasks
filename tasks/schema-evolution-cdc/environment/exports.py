"""Optional object-store export helpers (legacy)."""

from __future__ import annotations

import json
from pathlib import Path


def export_catalog_snapshot(root: str | Path, payload: dict) -> None:
    out = Path(root).parent / "store" / "exports"
    out.mkdir(parents=True, exist_ok=True)
    (out / "catalog_snapshot.json").write_text(json.dumps(payload, sort_keys=True) + "\n")
