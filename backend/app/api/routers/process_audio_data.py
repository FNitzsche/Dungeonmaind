"""REST API router for audio file upload and transcription."""

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.base_models.process_audio_data_base_models import (
    TranscriptionResponse,
    UploadAudioFileToDBResponse,
)
from app.functions.process_audio_data.extract_audio_metadata import extract_audio_metadata
from app.functions.process_audio_data.transcribe_audio import transcribe_audio

router = APIRouter()


@router.post('/uploadAudioFileToDB', response_model=UploadAudioFileToDBResponse)
async def upload_audio_file(audio: UploadFile = File(...)) -> UploadAudioFileToDBResponse:
    """Upload an audio file and extract its metadata.

    Args:
        audio (UploadFile): The uploaded audio file.

    Returns:
        UploadAudioFileToDBResponse: UploadAudioFileToDBResponse with filename, content type, and size.
    """
    try:
        # Read file contents
        audio_bytes = await audio.read()

        # TODO change 'extract_audio_metadata' method to a 'save to DB logic' since this is just a placeholder
        # Extract metadata via helper
        metadata = extract_audio_metadata(
            audio_bytes, filename=audio.filename, content_type=audio.content_type
        )

        return UploadAudioFileToDBResponse(output='This is a placeholder output', **metadata)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post('/transcribeAudioFile', response_model=TranscriptionResponse)
async def transcribe_audio_file(audio: UploadFile = File(...)) -> TranscriptionResponse:
    """Transcribe an uploaded audio file using WhisperX.

    Args:
        audio (UploadFile): The uploaded audio file.

    Returns:
        TranscriptionResponse: TranscriptionResponse with a list of transcribed segments.
    """
    try:
        audio_bytes = await audio.read()
        transcription = await transcribe_audio(audio_bytes, content_type=audio.content_type)
        return TranscriptionResponse(output=transcription)

    except Exception as e:
        print(e)
        raise HTTPException(status_code=500, detail=str(e))
