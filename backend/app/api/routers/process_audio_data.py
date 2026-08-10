from fastapi import APIRouter, HTTPException, UploadFile, File
from app.base_models.process_audio_data_base_models import UploadAudioFileToDBResponse, TranscriptionResponse
from app.functions.process_audio_data.transcribe_audio import transcribe_audio
from app.functions.process_audio_data.extract_audio_metadata import extract_audio_metadata

from app.functions.embedding.embedding_model import (
    delete_transcription_embeddings,
)

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


@router.post(
    "/transcribeAudioFile",
    response_model=TranscriptionResponse,
)
async def transcribe_audio_file(
    audio: UploadFile = File(...),
    replace_existing: bool = True,
    time_offset: float = 0.0,
) -> TranscriptionResponse:
    """
    Transcribe an uploaded audio file and store its timestamped
    transcription segments in ChromaDB.

    When replace_existing is true, transcription data belonging to the
    previous test/session is removed before processing the new audio.
    """

    if not audio.content_type or not audio.content_type.startswith(
        "audio/"
    ):
        raise HTTPException(
            status_code=415,
            detail="The uploaded file must be an audio file.",
        )

    try:
        audio_bytes = await audio.read()

        if not audio_bytes:
            raise HTTPException(
                status_code=400,
                detail="The uploaded audio file is empty.",
            )

        if replace_existing:
            delete_transcription_embeddings()

        transcription = await transcribe_audio(
            audio_bytes,
            content_type=audio.content_type,
            time_offset=time_offset,
        )

        return TranscriptionResponse(
            output=transcription,
        )

    except HTTPException:
        raise

    except Exception as error:
        print(error)

        raise HTTPException(
            status_code=500,
            detail=str(error),
        ) from error
