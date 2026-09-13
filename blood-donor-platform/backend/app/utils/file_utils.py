"""
Secure handling of the mandatory hospital-approval-document upload.

Validates content-type and size *before* touching disk, writes to a
per-upload UUID-named file (never trusts the client-supplied filename, which
prevents path traversal and filename collisions), and keeps uploads outside
any publicly-served static directory -- they are only ever returned via the
authenticated download endpoint in blood_request_routes.py.
"""
import os
import uuid

from fastapi import HTTPException, UploadFile, status

from app.core.config import settings

_MAX_BYTES = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024


async def save_hospital_approval_document(file: UploadFile) -> tuple[str, str]:
    """
    Validates and persists the uploaded file.
    Returns (stored_relative_path, content_type).
    Raises HTTPException(400) on any validation failure.
    """
    if file.content_type not in settings.allowed_upload_types_list:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Unsupported file type '{file.content_type}'. "
                f"Allowed types: {', '.join(settings.allowed_upload_types_list)}"
            ),
        )

    contents = await file.read()
    if len(contents) > _MAX_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File too large. Maximum allowed size is {settings.MAX_UPLOAD_SIZE_MB}MB.",
        )
    if len(contents) == 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty.")

    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    extension = _extension_for_content_type(file.content_type)
    stored_filename = f"{uuid.uuid4().hex}{extension}"
    stored_path = os.path.join(settings.UPLOAD_DIR, stored_filename)

    with open(stored_path, "wb") as out_file:
        out_file.write(contents)

    return stored_path, file.content_type


def _extension_for_content_type(content_type: str) -> str:
    return {
        "application/pdf": ".pdf",
        "image/jpeg": ".jpg",
        "image/jpg": ".jpg",
        "image/png": ".png",
    }.get(content_type, "")
