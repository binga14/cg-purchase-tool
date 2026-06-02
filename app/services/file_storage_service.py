import re
import shutil
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile


def sanitize_filename(filename: str) -> str:
    name = Path(filename).name.strip()
    safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", name)
    return safe_name or "upload"


def build_stored_filename(original_filename: str) -> str:
    safe_name = sanitize_filename(original_filename)
    return f"{uuid4().hex}_{safe_name}"


def save_upload_file(upload_file: UploadFile, upload_dir: Path, stored_filename: str) -> Path:
    upload_dir.mkdir(parents=True, exist_ok=True)
    destination = upload_dir / stored_filename

    with destination.open("wb") as output_file:
        shutil.copyfileobj(upload_file.file, output_file)

    return destination
