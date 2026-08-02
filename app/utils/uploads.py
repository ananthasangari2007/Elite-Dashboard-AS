from pathlib import Path
from uuid import uuid4

from flask import current_app
from werkzeug.utils import secure_filename


ALLOWED_EXTENSIONS = {"pdf", "png", "jpg", "jpeg"}


def save_uploaded_file(file_storage, folder):
    if not file_storage or not file_storage.filename:
        return None

    original_name = secure_filename(file_storage.filename)
    extension = original_name.rsplit(".", 1)[-1].lower() if "." in original_name else ""
    if extension not in ALLOWED_EXTENSIONS:
        raise ValueError("Unsupported file type. Upload only JPG, JPEG, PNG, or PDF files.")

    upload_root = Path(current_app.root_path) / "static" / "uploads" / folder
    upload_root.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid4().hex}_{original_name}"
    destination = upload_root / filename
    file_storage.save(destination)
    return f"/static/uploads/{folder}/{filename}"


def save_uploaded_proof_files(file_storage_list, limit=10):
    if not file_storage_list:
        raise ValueError("Please upload at least one proof file.")

    uploaded_paths = []
    selected_files = list(file_storage_list)[:limit]
    for file_storage in selected_files:
        if not file_storage or not file_storage.filename:
            continue
        saved_path = save_uploaded_file(file_storage, "submissions")
        if saved_path:
            uploaded_paths.append(saved_path)

    if not uploaded_paths:
        raise ValueError("No valid proof files were uploaded. Use JPG, JPEG, PNG, or PDF files only.")

    return "|".join(uploaded_paths)
