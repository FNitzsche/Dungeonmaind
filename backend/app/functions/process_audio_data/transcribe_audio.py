"""Audio transcription using WhisperX with speaker diarization and timeline event extraction."""

# WhisperX is not compatible with python3.13.
# It requires: Python 3.12
# ffmpeg installation necessary
# For GPU support:   https://developer.nvidia.com/cuda-12-8-1-download-archive (CUDA Toolkit 12.8.1)
#                   https://developer.nvidia.com/cudnn-downloads (cuDNN 9.10.2)
#                   (ctranslate2==4.6.0)
#                   pip uninstall torch torchaudio
#                   pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu128

import os

os.environ['TORCH_FORCE_WEIGHTS_ONLY_LOAD'] = '0'

import tempfile
from io import BytesIO
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.core.config import settings
from app.domain.store import store
from app.domain.timeline_store import timeline_store
from app.functions.embedding.embedding_model import embedd_transcriptions
from app.functions.llm.event_extractor import extract_events_from_transcriptions

torch: Any = None
whisperx: Any = None
AudioSegment: Any = None
DiarizationPipeline: Any = None

model_dir = os.getenv('WHISPERX_MODELS_DIR', None)
print('WHISPERX_MODELS_DIR:', os.getenv('WHISPERX_MODELS_DIR'))

device = 'cpu'
compute_type = 'int8'
if model_dir is not None:
    print('Warning: With Docker currently only CPU support is possible')

print(
    f'Transcription models will load on first transcription using device: {device} '
    f'with compute type: {compute_type}'
)

# Use a dictionary to cache alignment models by language to avoid reloading.
alignment_models_cache = {}
transcription_model = None
diarize_model = None


def load_audio_dependencies() -> None:
    """Import heavy audio libraries only when transcription is requested."""
    global torch, whisperx, AudioSegment, DiarizationPipeline, device, compute_type

    if whisperx is not None and torch is not None and AudioSegment is not None:
        return

    import lightning_fabric.utilities.cloud_io
    import torch as torch_module
    torch_module.serialization._default_to_weights_only = lambda pickle_module: False
    import whisperx as whisperx_module
    from pydub import AudioSegment as AudioSegmentClass
    from whisperx.diarize import DiarizationPipeline as DiarizationPipelineClass

    original_pl_load = lightning_fabric.utilities.cloud_io._load

    def patched_pl_load(path_or_url, map_location=None, weights_only=None):
        return original_pl_load(path_or_url, map_location, weights_only=False)

    lightning_fabric.utilities.cloud_io._load = patched_pl_load

    torch = torch_module
    whisperx = whisperx_module
    AudioSegment = AudioSegmentClass
    DiarizationPipeline = DiarizationPipelineClass

    if model_dir is None:
        device = 'cuda' if torch.cuda.is_available() else 'cpu'
        compute_type = 'float16' if device == 'cuda' else 'int8'

    ffmpeg_path = getattr(settings, 'ffmpeg_path', None)
    if ffmpeg_path:
        AudioSegment.converter = ffmpeg_path
        AudioSegment.ffmpeg = ffmpeg_path


def load_transcription_model() -> object:
    """Load the WhisperX transcription model based on settings.

    Returns:
        object: Loaded WhisperX transcription model.
    """
    new_model = whisperx.load_model(
        settings.transcription_model,
        device,
        compute_type=compute_type,
        download_root=model_dir,  # If None, uses default HF cache
    )
    if device == 'cuda':
        torch.cuda.empty_cache()
    return new_model


def reload_transcription_model():
    """Reload the transcription model (used when model setting changes)."""
    global transcription_model
    transcription_model = load_transcription_model()


def load_diarize_model() -> object | None:
    """Load the speaker diarization pipeline if HF_TOKEN is configured.

    Returns:
        DiarizationPipeline | None: DiarizationPipeline instance or None if unavailable.
    """
    if not settings.enable_diarization:
        print('Speaker diarization disabled by configuration.')
        return None

    if not settings.hf_token:
        print('Warning: HF_TOKEN is not set. Speaker diarization disabled.')
        return None

    try:
        new_model = DiarizationPipeline(use_auth_token=settings.hf_token, device=device)
        return new_model
    except Exception as e:
        print(f'Warning: Failed to load diarization model ({e}). Speaker diarization disabled.')
        print('Visit https://hf.co/pyannote/speaker-diarization-3.1 and accept terms to enable it.')
        return None


def ensure_transcription_models_loaded() -> None:
    """Load WhisperX models only when transcription is requested."""
    global transcription_model, diarize_model

    load_audio_dependencies()

    if transcription_model is None:
        print(
            f'Loading transcription model on device: {device} with compute type: {compute_type}'
        )
        transcription_model = load_transcription_model()

    if diarize_model is None:
        diarize_model = load_diarize_model()

    if diarize_model is not None:
        print('Models loaded successfully.')
    else:
        print('Transcription model loaded (diarization disabled).')



async def _transcribe_raw_session_audio(
    audio_bytes: bytes, file_extension: str, batch_size: int
) -> list:
    """Transcribe the uploaded session audio without pydub voiceprint prep."""
    temp_audio_dir = Path(settings.backend_root_path) / 'data' / 'tmp_audio'
    temp_audio_dir.mkdir(parents=True, exist_ok=True)
    temp_audio_path = temp_audio_dir / f'upload_{uuid4().hex}.{file_extension}'
    temp_audio_path.write_bytes(audio_bytes)

    try:
        print(f'Loading raw session audio from {temp_audio_path}...')
        try:
            audio = whisperx.load_audio(str(temp_audio_path))
        except PermissionError as e:
            raise RuntimeError(
                f'Windows denied access while WhisperX was loading audio file {temp_audio_path}. '
                'Close other backend processes, antivirus/file scanners may be locking the temp audio, '
                'then try again.'
            ) from e
        except FileNotFoundError as e:
            raise RuntimeError(
                'WhisperX could not find ffmpeg/ffprobe or the temporary audio file while loading audio. '
                f'Temporary audio path was {temp_audio_path}.'
            ) from e

        result = transcription_model.transcribe(audio, batch_size=batch_size)
        language_code = result['language']
        if language_code not in alignment_models_cache:
            print(f'Loading alignment model for language: {language_code}...')
            alignment_model, metadata = whisperx.load_align_model(
                language_code=language_code, device=device
            )
            alignment_models_cache[language_code] = (alignment_model, metadata)
        else:
            print(f'Using cached alignment model for language: {language_code}.')
            alignment_model, metadata = alignment_models_cache[language_code]

        print('Aligning...')
        result_aligned = whisperx.align(
            result['segments'],
            alignment_model,
            metadata,
            audio,
            device,
            return_char_alignments=False,
        )

        for segment in result_aligned.get('segments', []):
            segment['player_name'] = segment.get('speaker', 'unknown')
            segment['speaker'] = segment.get('speaker', 'unknown')

        for seg in result_aligned.get('segments', []):
            print(f'[{seg["start"]:.2f}s - {seg["end"]:.2f}s] {seg["speaker"]}: {seg["text"]}')

        filtered_segments = result_aligned.get('segments', [])
        texts = []
        speakers = []
        start_times = []

        for seg in filtered_segments:
            text = seg.get('text', '').strip()
            if not text:
                continue
            texts.append(text)
            speakers.append(seg.get('speaker', 'unknown'))
            start_times.append(float(seg.get('start', 0.0)))

        if texts:
            embedd_transcriptions(embedding_text=texts, speakers=speakers)

            events = extract_events_from_transcriptions(
                texts=texts,
                speakers=speakers,
                chunk_start_times=start_times,
            )
            if events:
                await timeline_store.add_events(events)
                print(f'Generated {len(events)} timeline events from transcription.')

        return filtered_segments
    finally:
        try:
            temp_audio_path.unlink(missing_ok=True)
        except PermissionError:
            print(f'Warning: Could not delete temporary audio file because it is locked: {temp_audio_path}')


async def transcribe_audio(
    audio_bytes: bytes, content_type: str, batch_size: int = 16
) -> list | None:
    """Transcribe audio bytes with speaker diarization and voiceprint recognition.

    Combines player voiceprints with session audio, performs WhisperX transcription,
    aligns word timestamps, assigns speakers via diarization, embeds the transcribed
    text, and extracts timeline events.

    Args:
        audio_bytes: Raw audio bytes.
        content_type: MIME type of the audio.
        batch_size (int): Batch size for WhisperX transcription.

    Returns:
        list | None: List of filtered segments with speaker labels, or None on error.
    """
    ensure_transcription_models_loaded()

    # Robust content type parsing and saving bytes to a temporary file
    file_extension_map = {'ogg': 'ogg', 'webm': 'webm', 'wav': 'wav', 'mpeg': 'mp3', 'mp4': 'mp4'}
    fileExtension = 'webm'
    for key in file_extension_map:
        if key in content_type:
            fileExtension = file_extension_map[key]
            break

    if not settings.enable_diarization:
        return await _transcribe_raw_session_audio(audio_bytes, fileExtension, batch_size)

    players = await store.list_players()
    print(len(players))

    combined_audio = AudioSegment.silent(duration=1000)
    speaker_order = []  # Kombiniere alle Voiceprints von den Spieler
    for p in players:
        if p.voiceprint is None:
            continue  # Spieler ohne Voiceprint überspringen

        voice_bytes = p.voiceprint.audio_bytes
        note = AudioSegment.from_file(BytesIO(voice_bytes))
        combined_audio += note + AudioSegment.silent(duration=500)
        speaker_order.append(p.name)  # Kombiniere die Session-Aufnahme

    session_audio = AudioSegment.from_file(BytesIO(audio_bytes))
    intro_duration_ms = len(combined_audio)
    combined_audio += session_audio
    # export
    output_buffer = BytesIO()
    combined_audio.export(output_buffer, format='wav')
    output_buffer.seek(0)

    print('Combining player voice notes with session audio...')
    combined_audio_buffer = output_buffer
    intro_duration_s = intro_duration_ms / 1000  # Umwandeln in Sekunden

    speaker_map = {f'SPEAKER_{i:02d}': name for i, name in enumerate(speaker_order)}
    print(speaker_map)

    print('Loading audio...')

    # 2. Save bytes to a temporary file (required by whisperx.load_audio)
    with tempfile.NamedTemporaryFile(suffix=f'.{fileExtension}', delete=False) as tempAudio:
        tempAudio.write(combined_audio_buffer.read())
        tempAudio.flush()
        tempAudioPath = tempAudio.name

    try:
        # Load audio from the temporary file
        audio = whisperx.load_audio(tempAudioPath)

        # 3. Transcribe using the cached model
        result = transcription_model.transcribe(audio, batch_size=batch_size)
        # print("Transcription segments:", result["segments"])

        # 4. Align whisper output to improve the word-level timestamps in transcription.
        language_code = result['language']
        if language_code not in alignment_models_cache:
            print(f'Loading alignment model for language: {language_code}...')
            alignment_model, metadata = whisperx.load_align_model(
                language_code=language_code, device=device
            )
            alignment_models_cache[language_code] = (alignment_model, metadata)
        else:
            print(f'Using cached alignment model for language: {language_code}.')
            alignment_model, metadata = alignment_models_cache[language_code]

        # 5. Perform alignment
        print('Aligning...')
        resultA = whisperx.align(
            result['segments'],
            alignment_model,
            metadata,
            audio,
            device,
            return_char_alignments=False,
        )
        # print("Aligned segments:", resultA["segments"])

        # 6. Assign speaker labels
        print('Assigning speakers...')

        # Min players is guaranteed to be available based on the user's requirement.
        min_players = max(len(speaker_order), 1)
        max_players = max(min_players + 2, store.group.max_size)
        print(f'min players: {min_players}')
        print(f'max players: {max_players}')

        # Perform diarization with constraints (skip if model unavailable)
        if diarize_model is not None:
            diarizeSegments = diarize_model(
                audio, min_speakers=min_players, max_speakers=max_players
            )
            resultB = whisperx.assign_word_speakers(diarizeSegments, resultA)
        else:
            resultB = resultA

        # print("Diarization segments:", diarizeSegments)

        # The final segments are the diarized result

        for segment in resultB.get('segments', []):
            original_speaker = segment.get('speaker', 'unknown')
            print(original_speaker)
            player_name = speaker_map.get(original_speaker, 'unknown')
            segment['player_name'] = player_name
            print('playername:', player_name)
            segment['speaker'] = player_name

        # print results
        for seg in resultB.get('segments', []):
            print(f'[{seg["start"]:.2f}s - {seg["end"]:.2f}s] {seg["speaker"]}: {seg["text"]}')

        # remove voice notes
        filtered_segments = [seg for seg in resultB['segments'] if seg['start'] > intro_duration_s]

        # 7. Embed the resulting text
        texts = []
        speakers = []
        start_times = []

        for seg in filtered_segments:
            text = seg.get('text', '').strip()
            if not text:
                continue

            texts.append(text)
            speakers.append(seg.get('speaker', 'unknown'))
            start_times.append(float(seg.get('start', 0.0)))

        if texts:
            embedd_transcriptions(embedding_text=texts, speakers=speakers)

            events = extract_events_from_transcriptions(
                texts=texts,
                speakers=speakers,
                chunk_start_times=start_times,
            )
            if events:
                await timeline_store.add_events(events)
                print(f'Generated {len(events)} timeline events from transcription.')

        return filtered_segments

        # # Return the diarized segments
        # return final_segments

    except Exception as e:
        print(f'An error occurred during transcription: {e}')
        raise

    finally:
        # Clean up the temporary file
        os.remove(tempAudioPath)
