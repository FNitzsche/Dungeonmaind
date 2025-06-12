#WhisperX is not compatible with python3.13.
#It requires: Python >=3.9 and <3.13
#ffmpeg installation necessary

import whisperx

#using for now a random audio file to test the implemented transcription function
def audio_transcribe(audio_file = r"C:\Dungeonmaind\backend\audio_file\audio_for_test.mp3", device = "cpu", compute_type = "int8", batch_size = 16):

    print("Loading WhisperX")
    # 1. Transcribe with original whisper (batched)
    model = whisperx.load_model("base", device, compute_type = compute_type)

    # save model to local path (optional)
    # model_dir = "/path/"
    # model = whisperx.load_model("large-v2", device, compute_type=compute_type, download_root=model_dir)

    print("Loading audio...")

    audio = whisperx.load_audio(audio_file)
    result = model.transcribe(audio, batch_size = batch_size)
    print(result["segments"])

    # delete model if low on GPU resources
    # import gc; import torch; gc.collect(); torch.cuda.empty_cache(); del model

    print("aligning..")
    # 2. Align whisper output to improve the word-level timestamps in your transcription.
    model_a, metadata = whisperx.load_align_model(language_code=result["language"], device=device)
    result_a = whisperx.align(result["segments"], model_a, metadata, audio, device, return_char_alignments=False)
    print(result_a["segments"])

    return result_a["segments"]

#run to test
#if __name__ == "__main__":
#    segments = audio_transcribe()
#    for seg in segments:
#        print(f"{seg['start']:.2f} - {seg['end']:.2f}: {seg['text']}")

