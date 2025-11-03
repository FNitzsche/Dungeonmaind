#WhisperX is not compatible with python3.13.
#It requires: Python 3.12
#ffmpeg installation necessary
#For GPU support:   https://developer.nvidia.com/cuda-12-8-1-download-archive (CUDA Toolkit 12.8.1)
#                   https://developer.nvidia.com/cudnn-downloads (cuDNN 9.10.2)
#                   (ctranslate2==4.6.0)
#                   pip uninstall torch torchaudio
#                   pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu128

import torch
import whisperx
import tempfile
import os

from app.functions.embedding.embedding_model import embedd_transcriptions
from app.domain.store import store

from app.core.config import settings

from pydub import AudioSegment
from io import BytesIO
import glob

def combine_voice_notes_with_session(audio_bytes: bytes, voice_notes_dir="C:/Users/lilia/Desktop/Uni/GitHub/Dungeonmaind/backend/uploads/voice_notes") -> BytesIO:
    # load voice notes
    voice_files = sorted(glob.glob(os.path.join(voice_notes_dir, "*.wav")))
    # List of player names with order
    speaker_order = []  

    combined_audio = AudioSegment.silent(duration=1000)
    # combine all voice notes
    for file_path in voice_files:
        note = AudioSegment.from_file(file_path)
        combined_audio += note + AudioSegment.silent(duration=500)  #pause inbetween voice notes
        #extract player name from file
        player_name = os.path.splitext(os.path.basename(file_path))[0]
        speaker_order.append(player_name)

    # add to the recorded session audio
    session_audio = AudioSegment.from_file(BytesIO(audio_bytes))
    # length of Voice Notes + pauses to later remove from transcribed audio
    intro_duration_ms = len(combined_audio)  
    combined_audio += session_audio

    output_buffer = BytesIO()
    combined_audio.export(output_buffer, format="wav")
    output_buffer.seek(0)
    return output_buffer, speaker_order, intro_duration_ms


def transcribe_audio(audio_bytes: bytes, batch_size=16):

    model_dir = os.getenv("WHISPERX_MODELS_DIR", None)

    print("WHISPERX_MODELS_DIR:", os.getenv("WHISPERX_MODELS_DIR"))

    if model_dir is None:
        # Dev/local environment: auto-detect device
        device = "cuda" if torch.cuda.is_available() else "cpu"
        compute_type = "float16" if device == "cuda" else "int8"
    else:
        # Docker: CPU-only setup
        device = "cpu"
        compute_type = "int8"
        print("Warning: With Docker currently only CPU support is possible")

    print("Loading WhisperX model...")
    model = whisperx.load_model(
        "base",  # or "medium.en", "large-v2", etc.
        device,
        compute_type=compute_type,
        download_root=model_dir  # If None, uses default HF cache
    )
    # 1. Load the model

    print("Loading WhisperX")
    model = whisperx.load_model(settings.transcription_model, device, compute_type=compute_type)
    # save model to local path (optional)
    # model_dir = "/path/"
    # model = whisperx.load_model("large-v2", device, compute_type=compute_type, download_root=model_dir)

    #combine notes and session recording audio
    print("Combining player voice notes with session audio...")
    combined_audio_buffer, speaker_order, intro_duration_ms = combine_voice_notes_with_session(audio_bytes)
    intro_duration_s = intro_duration_ms / 1000.0  # Umwandeln in Sekunden

    speaker_map = {f"SPEAKER_{i:02d}": name for i, name in enumerate(speaker_order)} 
    
    print(speaker_map)

    # 2. Save bytes to a temporary file (required by whisperx.load_audio)
    print("Loading audio...")
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_audio:
        temp_audio.write(combined_audio_buffer.read())
        temp_audio.flush()
        audio = whisperx.load_audio(temp_audio.name)

    
    # with tempfile.NamedTemporaryFile(suffix=".mp3",delete=False) as temp_audio:
    #     temp_audio.write(audio_bytes)
    #     temp_audio.flush()
    #     audio = whisperx.load_audio(temp_audio.name)

    # 3. Transcribe
    result = model.transcribe(audio, batch_size=batch_size)
    
    print(result["segments"])
    # delete model if low on GPU resources
    # import gc; import torch; gc.collect(); torch.cuda.empty_cache(); del model

    # 4. Align whisper output to improve the word-level timestamps in transcription.
    print("Aligning...")
    model_a, metadata = whisperx.load_align_model(language_code=result["language"], device=device)
    result_a = whisperx.align(result["segments"], model_a, metadata, audio, device, return_char_alignments=False)
    print(result_a["segments"])

    texts = [segment['text'] for segment in result_a["segments"]]
    embedd_transcriptions(texts)
    
    # 5. Assign speaker labels
    print("Assigning...")
    
    #created a HF token and then added it
    diarize_model = whisperx.diarize.DiarizationPipeline(use_auth_token="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", device=device)
    
    g = store.group
    max_players = g.max_size

    #add min/max number of speakers
    diarize_segments = diarize_model(audio, min_speakers=1, max_speakers=2)

    result_b = whisperx.assign_word_speakers(diarize_segments, result_a)
    print(diarize_segments)
    print(result_b["segments"]) #segments are now assigned speaker IDs

    for segment in result_b["segments"]:
        original_speaker = segment["speaker"]
        player_name = speaker_map.get(original_speaker, "unkown")
        segment["player_name"] = player_name
        segment["speaker"] = player_name

    #remove voice notes
    filtered_segments = [seg for seg in result_b["segments"] if seg["start"] > intro_duration_s]

    print(f"Removed intro (first {intro_duration_s:.2f} seconds). Remaining segments: {len(filtered_segments)}")

    return filtered_segments


#run only to test function
if __name__ == "__main__":
    # Load any mp3 file into bytes
    with open("C:/Users/lilia/Desktop/Uni/GitHub/Dungeonmaind/backend/app/functions/process_audio_data/test.mp3", "rb") as f:
        audio = f.read()

    segments = transcribe_audio(audio)
    
    # Print transcription
    for seg in segments:
        print(f"{seg['start']:.2f} - {seg['end']:.2f} [{seg['speaker']}]: {seg['text']}")
