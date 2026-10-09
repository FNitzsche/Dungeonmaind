# WhisperX requires Python 3.12 in this project.
# ffmpeg is required.
# Runtime device selection is automatic:
# - NVIDIA GPU exposed by Docker -> CUDA + float16
# - No CUDA GPU exposed -> CPU + int8
# Docker image uses PyTorch CUDA 12.6 and CTranslate2 4.6.3.

import torch
import whisperx
import tempfile
import os
from pydub import AudioSegment
from io import BytesIO
from pydub.exceptions import CouldntDecodeError
from app.functions.embedding.embedding_model import embedd_transcriptions
from app.domain.store import store
from app.core.config import settings
from whisperx.diarize import DiarizationPipeline

def load_transcription_model():
    new_model = whisperx.load_model(
        settings.transcription_model,
        device,
        compute_type=compute_type,
        language="en",
        download_root=model_dir  # If None, uses default HF cache
    )
    if device == "cuda":
        torch.cuda.empty_cache()
    return new_model


def reload_transcription_model():
    global transcription_model
    transcription_model = load_transcription_model()


def load_diarize_model():
    if not settings.hf_token:
        raise RuntimeError("HF_TOKEN is not set. Please add it to your .env file.")

    new_model = DiarizationPipeline(
        use_auth_token=settings.hf_token,
        device=device
    )
    return new_model


model_dir = os.getenv("WHISPERX_MODELS_DIR", None)
print("WHISPERX_MODELS_DIR:", os.getenv("WHISPERX_MODELS_DIR"))

device = "cuda" if torch.cuda.is_available() else "cpu"

if device == "cuda":
    compute_type = "float16"
    print(
        "CUDA detected. WhisperX will use GPU "
        "with float16 compute."
    )
else:
    compute_type = "int8"
    print(
        "CUDA not available. WhisperX will use CPU "
        "with int8 compute."
    )

print(f"Loading transcription and alignment models on device: {device} with compute type: {compute_type}")

# Use a dictionary to cache alignment models by language to avoid reloading
alignment_models_cache = {}

# 1. Load models
transcription_model = load_transcription_model()
diarize_model = load_diarize_model()
print("Models loaded successfully.")



def decode_audio_bytes(
    audio_bytes: bytes,
    content_type: str | None = None,
) -> AudioSegment:
    """
    Decode audio bytes safely.

    Tries the format from the MIME type first, then lets FFmpeg
    detect the format automatically.
    """

    if not audio_bytes:
        raise RuntimeError("The audio data is empty.")

    normalized_content_type = (content_type or "").casefold()

    possible_formats: list[str] = []

    if "webm" in normalized_content_type:
        possible_formats.append("webm")

    if "ogg" in normalized_content_type:
        possible_formats.append("ogg")

    if "mpeg" in normalized_content_type or "mp3" in normalized_content_type:
        possible_formats.append("mp3")

    if "wav" in normalized_content_type:
        possible_formats.append("wav")

    if "mp4" in normalized_content_type:
        possible_formats.append("mp4")

    if "m4a" in normalized_content_type:
        possible_formats.append("m4a")

    for audio_format in possible_formats:
        try:
            return AudioSegment.from_file(
                BytesIO(audio_bytes),
                format=audio_format,
            )
        except CouldntDecodeError:
            continue

    try:
        return AudioSegment.from_file(
            BytesIO(audio_bytes)
        )
    except CouldntDecodeError as error:
        raise RuntimeError(
            "The audio could not be decoded. "
            "Please use a valid WAV, MP3, OGG, WebM, M4A, or MP4 file."
        ) from error





async def transcribe_audio(
    audio_bytes: bytes,
    content_type: str,
    batch_size: int = 4,
    time_offset: float = 0.0,
):
    print("==========================================")
    print("STARTING AUDIO TRANSCRIPTION")
    print("==========================================")

    players = await store.list_players()

    print(f"Number of players: {len(players)}")
    print(f"Device: {device}")
    print(f"Compute type: {compute_type}")
    print(f"Batch size: {batch_size}")

    # -----------------------------------------------------
    # 1. Decode ONLY the actual session audio
    # -----------------------------------------------------

    session_audio = decode_audio_bytes(
        audio_bytes,
        content_type=content_type,
    )

    print(
        f"Session audio duration: "
        f"{len(session_audio) / 1000:.2f} seconds"
    )

    # Convert to a standard format before WhisperX:
    # mono + 16 kHz.
    session_audio = (
        session_audio
        .set_channels(1)
        .set_frame_rate(16000)
        .set_sample_width(2)
    )

    # # Debug file
    # session_audio.export(
    #     "/tmp/debug_session_audio.wav",
    #     format="wav",
    # )

    # -----------------------------------------------------
    # 2. Save WAV temporarily
    # -----------------------------------------------------

    output_buffer = BytesIO()

    session_audio.export(
        output_buffer,
        format="wav",
    )

    output_buffer.seek(0)

    with tempfile.NamedTemporaryFile(
        suffix=".wav",
        delete=False,
    ) as temp_audio:

        temp_audio.write(
            output_buffer.read()
        )

        temp_audio.flush()

        temp_audio_path = temp_audio.name

    try:
        # -------------------------------------------------
        # 3. Load audio for WhisperX
        # -------------------------------------------------

        print("Loading audio into WhisperX...")

        audio = whisperx.load_audio(
            temp_audio_path
        )

        print(
            f"Whisper audio samples: {len(audio)}"
        )

        print(
            f"Whisper audio duration: "
            f"{len(audio) / 16000:.2f} seconds"
        )

        # -------------------------------------------------
        # 4. Whisper transcription
        # -------------------------------------------------

        print("Running Whisper transcription...")

        result = transcription_model.transcribe(
            audio,
            batch_size=batch_size,
            language="en",
        )

        print("")
        print("RAW WHISPER TRANSCRIPTION:")
        print("------------------------------------------")

        raw_segments = result.get(
            "segments",
            [],
        )

        if not raw_segments:
            print(
                "WARNING: Whisper returned no segments."
            )

        for segment in raw_segments:
            print(
                f"[{segment.get('start', 0):.2f}s - "
                f"{segment.get('end', 0):.2f}s] "
                f"{segment.get('text', '')}"
            )

        print("------------------------------------------")

        # -------------------------------------------------
        # 5. Alignment
        # -------------------------------------------------

        language_code = result.get(
            "language",
            "en",
        )

        if language_code not in alignment_models_cache:

            print(
                f"Loading alignment model "
                f"for language: {language_code}..."
            )

            alignment_model, metadata = (
                whisperx.load_align_model(
                    language_code=language_code,
                    device=device,
                )
            )

            alignment_models_cache[
                language_code
            ] = (
                alignment_model,
                metadata,
            )

        else:

            print(
                f"Using cached alignment model "
                f"for language: {language_code}."
            )

            alignment_model, metadata = (
                alignment_models_cache[
                    language_code
                ]
            )

        print("Aligning...")

        result_aligned = whisperx.align(
            result["segments"],
            alignment_model,
            metadata,
            audio,
            device,
            return_char_alignments=False,
        )

        # -------------------------------------------------
        # 6. Diarization
        # -------------------------------------------------

        print("Assigning speakers...")

        # We know how many currently registered players
        # exist, but do not force WhisperX to invent six
        # speakers for a single-speaker recording.

        active_player_count = max(
            len(players),
            1,
        )

        min_players = 1

        max_players = max(
            active_player_count,
            2,
        )

        print(
            f"min players: {min_players}"
        )

        print(
            f"max players: {max_players}"
        )

        diarize_segments = diarize_model(
            audio,
            min_speakers=min_players,
            max_speakers=max_players,
        )

        result_with_speakers = (
            whisperx.assign_word_speakers(
                diarize_segments,
                result_aligned,
            )
        )

        # -------------------------------------------------
        # 7. Build player mapping
        # -------------------------------------------------

        players_with_voiceprints = [
            player
            for player in players
            if player.voiceprint is not None
        ]

        speaker_map = {
            f"SPEAKER_{index:02d}": player.name
            for index, player
            in enumerate(players_with_voiceprints)
        }

        print(
            "Speaker map:",
            speaker_map,
        )

        # -------------------------------------------------
        # 8. Normalize resulting segments
        # -------------------------------------------------

        final_segments = []

        for segment in result_with_speakers.get(
            "segments",
            [],
        ):

            text = (
                segment
                .get("text", "")
                .strip()
            )

            if not text:
                continue

            original_speaker = segment.get(
                "speaker",
                "unknown",
            )

            # If Whisper speaker matches one of the
            # registered voiceprint speakers.
            if original_speaker in speaker_map:

                player_name = speaker_map[
                    original_speaker
                ]

            # Single-player session:
            # safely associate speech with that player.
            elif len(players) == 1:

                player_name = players[0].name

            else:

                player_name = "unknown"

            start = max(
                0.0,
                float(
                    segment.get(
                        "start",
                        0.0,
                    )
                )
                + time_offset,
            )

            end = max(
                0.0,
                float(
                    segment.get(
                        "end",
                        0.0,
                    )
                )
                + time_offset,
            )

            normalized_segment = dict(
                segment
            )

            normalized_segment[
                "start"
            ] = start

            normalized_segment[
                "end"
            ] = end

            normalized_segment[
                "speaker"
            ] = player_name

            normalized_segment[
                "player_name"
            ] = player_name

            final_segments.append(
                normalized_segment
            )

            print(
                f"[{start:.2f}s - "
                f"{end:.2f}s] "
                f"{player_name}: "
                f"{text}"
            )

        # -------------------------------------------------
        # 9. Save transcription to ChromaDB
        # -------------------------------------------------

        texts: list[str] = []
        speakers: list[str] = []
        start_times: list[float] = []
        end_times: list[float] = []

        for segment in final_segments:

            text = (
                segment
                .get("text", "")
                .strip()
            )

            if not text:
                continue

            texts.append(
                text
            )

            speakers.append(
                segment.get(
                    "speaker",
                    "unknown",
                )
            )

            start_times.append(
                float(
                    segment.get(
                        "start",
                        0.0,
                    )
                )
            )

            end_times.append(
                float(
                    segment.get(
                        "end",
                        0.0,
                    )
                )
            )

        if texts:

            print(
                f"Saving {len(texts)} "
                f"transcription segments..."
            )

            embedd_transcriptions(
                embedding_text=texts,
                speakers=speakers,
                start_times=start_times,
                end_times=end_times,
            )

        else:

            print(
                "WARNING: No transcription text "
                "was produced. Nothing will be "
                "saved to ChromaDB."
            )

        print("==========================================")
        print("TRANSCRIPTION FINISHED")
        print("==========================================")

        return final_segments

    except Exception as error:

        print(
            "An error occurred during "
            f"transcription: {error}"
        )

        raise RuntimeError(
            f"Audio transcription failed: {error}"
        ) from error

    finally:

        try:
            os.remove(
                temp_audio_path
            )
        except OSError:
            pass

