from __future__ import annotations
import subprocess
from pathlib import Path
import tempfile
from typing import List, Any

from app.functions.process_audio_data.chunk_accumulator import accumulator
from app.functions.process_audio_data.transcribe_audio import transcribe_audio

def _write_manifest(files: List[Path]) -> Path:
    manifest = Path(tempfile.gettempdir()) / f"concat_{files[0].parent.name}.txt"
    manifest.write_text("\n".join([f"file '{p.resolve().as_posix()}'" for p in files]), encoding="utf-8")
    return manifest

def _concat_to_wav(files: List[Path]) -> tuple[Path, Path]:
    if not files:
        raise RuntimeError("No chunk files to concatenate")
    out_wav = files[0].parent / f"{files[0].parent.name}.wav"
    manifest = _write_manifest(files)
    cmd = [
        "ffmpeg",
        "-hide_banner", "-loglevel", "error",
        "-f", "concat", "-safe", "0",
        "-i", str(manifest),
        "-ac", "1", "-ar", "16000",
        "-acodec", "pcm_s16le",
        str(out_wav),
    ]
    subprocess.run(cmd, check=True)
    return out_wav, manifest

async def process_session(session_id: str) -> Any:
    files = await accumulator.list_chunks(session_id)
    if not files:
        return {"message": "no chunks"}
    wav = None
    manifest = None
    try:
        wav, manifest = _concat_to_wav(files)
        result = transcribe_audio(
            audio_bytes=wav.read_bytes(),
            content_type="audio/wav",
            filename=wav.name,
        )
        return result
    finally:
        # cleanup temp artifacts and session folder
        try:
            if manifest and manifest.exists():
                manifest.unlink(missing_ok=True)  # py>=3.8
        except Exception:
            pass
        try:
            if wav and wav.exists():
                wav.unlink(missing_ok=True)
        except Exception:
            pass
        await accumulator.clear_session(session_id)
