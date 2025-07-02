#WhisperX is not compatible with python3.13.
#It requires: Python >=3.9 and <3.13
#ffmpeg installation necessary

import torch
import whisperx
import tempfile

def transcribe_audio(audio_bytes: bytes, compute_type="int8", batch_size=16):

    #set default device to GPU
    device = "cuda" if torch.cuda.is_available() else "cpu"
    # 1. Load the model
    print("Loading WhisperX")
    model = whisperx.load_model("base", device, compute_type=compute_type)
    # save model to local path (optional)
    # model_dir = "/path/"
    # model = whisperx.load_model("large-v2", device, compute_type=compute_type, download_root=model_dir)

    # 2. Save bytes to a temporary file (required by whisperx.load_audio)
    print("Loading audio...")
    with tempfile.NamedTemporaryFile(suffix=".mp3",delete=False) as temp_audio:
        temp_audio.write(audio_bytes)
        temp_audio.flush()
        audio = whisperx.load_audio(temp_audio.name)

    # 3. Transcribe
    result = model.transcribe(audio, batch_size=batch_size)
    print(result["segments"])
    # delete model if low on GPU resources
    # import gc; import torch; gc.collect(); torch.cuda.empty_cache(); del model

    # 4. Align whisper output to improve the word-level timestamps in your transcription.
    print("Aligning...")
    model_a, metadata = whisperx.load_align_model(language_code=result["language"], device=device)
    result_a = whisperx.align(result["segments"], model_a, metadata, audio, device, return_char_alignments=False)
    print(result_a["segments"])

    return result_a["segments"]