from fastapi import APIRouter, HTTPException, UploadFile, File, Response, BackgroundTasks, Form
from app.base_models.process_audio_data_base_models import UploadAudioFileToDBResponse, TranscriptionResponse
from app.functions.process_audio_data.transcribe_audio import transcribe_audio
from app.functions.process_audio_data.extract_audio_metadata import extract_audio_metadata

router = APIRouter()

@router.post("/uploadAudioFileToDB", response_model=UploadAudioFileToDBResponse)
async def upload_audio_file(audio: UploadFile = File(...)):
    """
    Receives an audio file and returns metadata and placeholder transcription.
    """
    try:
        # Read file contents
        audio_bytes = await audio.read()

        # TODO change 'extract_audio_metadata' method to a 'save to DB logic' since this is just a placeholder
        # Extract metadata via helper
        metadata = extract_audio_metadata(
            audio_bytes,
            filename=audio.filename,
            content_type=audio.content_type
        )

        return UploadAudioFileToDBResponse(
            output="This is a placeholder output",
            **metadata
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/transcribeAudioFile", response_model=TranscriptionResponse)
async def transcribe_audio_file(audio: UploadFile = File(...)):
    """
    Transcribes an uploaded audio file and returns a text.
    """
    try:
        audio_bytes = await audio.read()
        MIN_BYTES = 4000  # ~ a few KB; tune as needed
        if not audio_bytes or len(audio_bytes) < MIN_BYTES:
            # Nothing useful to transcribe; avoid 500s and heavy startup
            return Response(status_code=204)

        transcription = transcribe_audio(audio_bytes)
        return TranscriptionResponse(output=transcription)

    except Exception as e:
        print(e)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/transcribeChunk", status_code=202)
async def transcribe_chunk(
    background_tasks: BackgroundTasks,
    audio: UploadFile = File(...),
    sessionId: str = Form(...),
    chunkIndex: int = Form(...)
):
    try:
        audio_bytes = await audio.read()
        MIN_BYTES = 4000
        if not audio_bytes or len(audio_bytes) < MIN_BYTES:
            return Response(status_code=204)

        # ⬇️ pass content_type & filename (so the transcriber picks correct suffix)
        background_tasks.add_task(
            transcribe_audio,
            audio_bytes,
            audio.content_type,
            audio.filename,
        )

        return {"status": "queued", "sessionId": sessionId, "chunkIndex": chunkIndex}
    except Exception as e:
        print(e)
        raise HTTPException(status_code=500, detail=str(e))

