"""Audio metadata extraction utilities."""


def extract_audio_metadata(audio_bytes: bytes, filename: str, content_type: str) -> dict:
    """Extract basic metadata from audio file bytes.

    Args:
        audio_bytes: Raw audio byte data.
        filename: Original filename of the audio.
        content_type: MIME type of the audio.

    Returns:
        Dict with filename, content_type, and size_bytes.
    """
    return {'filename': filename, 'content_type': content_type, 'size_bytes': len(audio_bytes)}
