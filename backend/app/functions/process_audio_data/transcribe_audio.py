#WhisperX is not compatible with python3.13.
#It requires: Python 3.12
#ffmpeg installation necessary
#For GPU support:   https://developer.nvidia.com/cuda-12-8-1-download-archive (CUDA Toolkit 12.8.1)
#                   https://developer.nvidia.com/cudnn-downloads (cuDNN 9.10.2)
#                   (ctranslate2==4.6.0)
#                   pip uninstall torch torchaudio
#                   pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu128

import os
import tempfile

import torch
import whisperx

from app.core.config import settings
from app.functions.embedding.embedding_model import embedd_text
from functools import lru_cache


def _resolve_device_and_precision():
    """
    Decide device/compute_type based on env and availability.
    Returns: (device:str, compute_type:str, model_dir: Optional[str])
    """
    model_dir = os.getenv("WHISPERX_MODELS_DIR", None)
    print("WHISPERX_MODELS_DIR:", model_dir)

    if model_dir is None:
        # Dev/local environment: auto-detect device
        device = "cuda" if torch.cuda.is_available() else "cpu"
        compute_type = "float16" if device == "cuda" else "int8"
    else:
        # Docker: CPU-only setup
        device = "cpu"
        compute_type = "int8"
        print("Warning: With Docker currently only CPU support is possible")

    return device, compute_type, model_dir


@lru_cache(maxsize=1)
def _get_whisperx_model(transcription_model: str, device: str, compute_type: str, model_dir: str | None):
    """
    Load WhisperX model once and cache it.
    The cache key includes (model name, device, compute_type, model_dir).
    """
    print("Loading WhisperX model (cached loader)...")
    return whisperx.load_model(
        transcription_model,
        device,
        compute_type=compute_type,
        download_root=model_dir  # If None, uses default HF cache
    )


@lru_cache(maxsize=8)
def _get_align_model(language_code: str, device: str):
    """
    Cache align model per (language_code, device).
    """
    return whisperx.load_align_model(language_code=language_code, device=device)


@lru_cache(maxsize=1)
def _get_diarizer(device: str):
    """
    Cache diarization pipeline once per device.
    NOTE: If you have your token in settings, prefer: settings.hf_token
    """
    # (kept your original token usage)
    return whisperx.diarize.DiarizationPipeline(
        use_auth_token="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",
        device=device
    )

def transcribe_audio(
    audio_bytes: bytes,
    content_type: str | None = None,   # ⬅️ new (optional for backward compat)
    filename: str | None = None,       # ⬅️ new (optional for backward compat)
    batch_size=16
):

    model_dir = os.getenv("WHISPERX_MODELS_DIR", None)
    print("WHISPERX_MODELS_DIR:", os.getenv("WHISPERX_MODELS_DIR"))

    if model_dir is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"
        compute_type = "float16" if device == "cuda" else "int8"
    else:
        device = "cpu"
        compute_type = "int8"
        print("Warning: With Docker currently only CPU support is possible")

    print("Loading WhisperX")
    model = whisperx.load_model(settings.transcription_model, device, compute_type=compute_type)

    suffix = ".mp3"
    ct = (content_type or "").lower()
    if "webm" in ct or "ogg" in ct:
        suffix = ".webm"
    elif "wav" in ct:
        suffix = ".wav"
    elif "mpeg" in ct or "mp3" in ct:
        suffix = ".mp3"
    elif filename:
        fn = filename.lower()
        if fn.endswith((".webm", ".ogg")): suffix = ".webm"
        elif fn.endswith(".wav"):          suffix = ".wav"
        elif fn.endswith(".mp3"):          suffix = ".mp3"

    # 2. Save bytes to a temporary file with the chosen suffix
    print("Loading audio...")
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as temp_audio:
        temp_audio.write(audio_bytes)
        temp_audio.flush()
        audio_path = temp_audio.name

    audio = whisperx.load_audio(audio_path)

    # 3. Transcribe (unchanged)
    result = model.transcribe(audio, batch_size=batch_size)
    print(result["segments"])

    # 4. Align (unchanged)
    print("Aligning...")
    model_a, metadata = whisperx.load_align_model(language_code=result["language"], device=device)
    result_a = whisperx.align(result["segments"], model_a, metadata, audio, device, return_char_alignments=False)
    print(result_a["segments"])

    texts = [segment['text'] for segment in result_a["segments"]]
    embedd_text(texts)

    # Diarization (unchanged)
    diarize_model = whisperx.diarize.DiarizationPipeline(
        use_auth_token="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", device=device
    )
    diarize_segments = diarize_model(audio)
    result_b = whisperx.assign_word_speakers(diarize_segments, result_a)
    print(diarize_segments)
    print(result_b["segments"])

    # (optional: clean up temp)
    try:
        os.remove(audio_path)
    except Exception:
        pass

    return result_b["segments"]
