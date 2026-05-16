"""JSON file helpers shared by evaluation utilities."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def write_json_file(path: Path, payload: Any) -> None:
    """Write pretty UTF-8 JSON with the newline convention used by eval outputs."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
