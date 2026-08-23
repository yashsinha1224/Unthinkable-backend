import uuid
from fastapi import UploadFile, HTTPException

from database.database import supabase

BUCKET = "complaint-photos"
ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_FILE_SIZE_MB = 5


async def upload_complaint_photo(file: UploadFile) -> str:
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(status_code=400, detail="Only JPEG, PNG, or WEBP images are allowed")

    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE_MB * 1024 * 1024:
        raise HTTPException(status_code=400, detail=f"Photo must be under {MAX_FILE_SIZE_MB}MB")

    if supabase is None:
        raise HTTPException(status_code=500, detail="Photo storage is not configured (missing supabase_url/supabase_key)")

    ext = file.filename.rsplit(".", 1)[-1] if file.filename and "." in file.filename else "jpg"
    path = f"{uuid.uuid4()}.{ext}"

    supabase.storage.from_(BUCKET).upload(path, contents, {"content-type": file.content_type})
    return supabase.storage.from_(BUCKET).get_public_url(path)