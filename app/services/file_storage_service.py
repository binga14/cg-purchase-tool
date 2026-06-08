import re
from pathlib import Path
from uuid import uuid4


def sanitize_filename(filename: str) -> str:
    name = Path(filename).name.strip()
    safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", name)
    return safe_name or "upload"


def build_stored_filename(original_filename: str) -> str:
    safe_name = sanitize_filename(original_filename)
    return f"{uuid4().hex}_{safe_name}"
