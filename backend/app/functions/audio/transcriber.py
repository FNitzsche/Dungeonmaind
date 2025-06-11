#WhisperX is not compatible with python3.13.
#It requires: Python >=3.9 and <3.13

import whisperx

def audio_transcribe(audio_file = "audio.mp3", device = "cpu", compute_type = "int8", batch_size = 16):

    # 1. Transcribe with original whisper (batched)
    model = whisperx.load_model("base", device, compute_type = compute_type)

    # save model to local path (optional)
    # model_dir = "/path/"
    # model = whisperx.load_model("large-v2", device, compute_type=compute_type, download_root=model_dir)


    audio = whisperx.load_audio(audio_file)
    result = model.transcribe(audio, batch_size = batch_size)
    print(result["segments"])

    # delete model if low on GPU resources
    # import gc; import torch; gc.collect(); torch.cuda.empty_cache(); del model

    # 2. Align whisper output
    model_a, metadata = whisperx.load_align_model(language_code=result["language"], device=device)
    result = whisperx.align(result["segments"], model_a, metadata, audio, device, return_char_alignments=False)
    print(result["segments"])

    return result

