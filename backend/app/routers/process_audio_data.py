from fastapi import APIRouter, HTTPException, UploadFile, File, Response, BackgroundTasks, Form
from app.base_models.process_audio_data_base_models import UploadAudioFileToDBResponse, TranscriptionResponse, \
    ChunkUploadResponse
from app.functions.process_audio_data.transcribe_audio import transcribe_audio
from app.functions.process_audio_data.extract_audio_metadata import extract_audio_metadata
from app.functions.process_audio_data.chunk_accumulator import accumulator
from app.functions.process_audio_data.audio_processor import process_session
from app.functions.utils.util import _guess_ext

router = APIRouter()



@router.post("/uploadAudioFileToDB", response_model=UploadAudioFileToDBResponse)
async def upload_audio_file(audio: UploadFile = File(...)):
    """
    Receives an audio file and returns metadata and placeholder transcription.
    """
    try:
        # Read file contents
        audio_bytes = await audio.read()

        # TODOO change 'extract_audio_metadata' method to a 'save to DB logic' since this is just a placeholder
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

        result = transcribe_audio(
            audio_bytes=audio_bytes,
            content_type=audio.content_type,
            filename=audio.filename,
        )
        return TranscriptionResponse(output=result)
        # result is whisperx dict; we only need segments for our response model

    except Exception as e:
        print(e)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/transcribeChunk", response_model=ChunkUploadResponse, status_code=202)
async def transcribe_chunk(
    background_tasks: BackgroundTasks,
    audio: UploadFile = File(...),
    sessionId: str = Form(...),
    chunkIndex: int = Form(...),
    durationMs: int | None = Form(None),
):
    try:
        audio_bytes = await audio.read()
        MIN_BYTES = 4000
        if not audio_bytes or len(audio_bytes) < MIN_BYTES:
            return Response(status_code=204)

        ready = await accumulator.add_chunk(
            session_id=sessionId,
            chunk_index=int(chunkIndex),
            data=audio_bytes,
            filename=(audio.filename or f"chunk{_guess_ext(audio)}"),
            duration_ms=durationMs,
        )

        if ready:
            background_tasks.add_task(process_session, sessionId)

        return {
            "status": "queued",
            "sessionId": sessionId,
            "chunkIndex": chunkIndex,
            "accumulating": not ready,
        }
    except Exception as e:
        print(e)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/flushSession", response_model=TranscriptionResponse)
async def flush_session(sessionId: str = Form(...)):
    """
    Force-process whatever chunks are currently accumulated for this session.
    """
    try:
        result = await process_session(sessionId)
        # process_session returns the list of segments from transcribe_audio()
        if isinstance(result, list):
            return TranscriptionResponse(output=result)
        # if something else comes back, normalize safely
        return TranscriptionResponse(output=(result or []))
    except Exception as e:
        print(e)
        raise HTTPException(status_code=500, detail=str(e))