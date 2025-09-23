# reoccurring functionalities can be added in this directory
from fastapi import UploadFile
from pathlib import Path

def _guess_ext(upload: UploadFile) -> str:
    if upload and upload.filename:
        ext = Path(upload.filename).suffix.lower()
        if ext:
            return ext
    ct = (upload.content_type or "").lower()
    if "wav" in ct:  return ".wav"
    if "webm" in ct or "ogg" in ct: return ".webm"
    if "mpeg" in ct or "mp3" in ct:  return ".mp3"
    return ".webm"