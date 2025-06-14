def extract_audio_metadata(audio_bytes: bytes, filename: str, content_type: str) -> dict:
    """
    Extract basic metadata from audio file bytes.
    """
    return {
        "filename": filename,
        "content_type": content_type,
        "size_bytes": len(audio_bytes),
    }
