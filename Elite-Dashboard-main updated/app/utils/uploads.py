from pathlib import Path
from uuid import uuid4

from flask import current_app
from werkzeug.utils import secure_filename


ALLOWED_EXTENSIONS = {"pdf", "doc", "docx", "png", "jpg", "jpeg", "zip", "txt"}


def save_uploaded_file(file_storage, folder):
    if not file_storage or not file_storage.filename:
        return None

    original_name = secure_filename(file_storage.filename)
    extension = original_name.rsplit(".", 1)[-1].lower() if "." in original_name else ""
    if extension not in ALLOWED_EXTENSIONS:
        raise ValueError("Unsupported file type.")

    upload_root = Path(current_app.root_path) / "static" / "uploads" / folder
    upload_root.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid4().hex}_{original_name}"
    destination = upload_root / filename
    file_storage.save(destination)
    return f"uploads/{folder}/{filename}"
