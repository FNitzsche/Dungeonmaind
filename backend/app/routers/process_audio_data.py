from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from app.base_models.process_audio_data_base_models import UploadAudioFileToDBResponse, TranscriptionResponse
from app.functions.process_audio_data.transcribe_audio import transcribe_audio
from app.functions.process_audio_data.extract_audio_metadata import extract_audio_metadata
import os
from fastapi import Request
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
        transcription = transcribe_audio(audio_bytes)
        return TranscriptionResponse(output=transcription)

    except Exception as e:
        print(e)
        raise HTTPException(status_code=500, detail=str(e))
    

# @router.post("/uploadVoiceNote")
# async def upload_voice_note(request: Request):
#     form = await request.form()
#     print("Form content:", dict(form))
#     return {"received_form": dict(form)}

@router.post("/uploadVoiceNote")
async def upload_voice_note(audio: UploadFile = File(...), player_id: str = Form(...), player_name: str = Form(None),):
    """
    Simple test: saves uploaded audio to 'uploads/voice_notes' to verify connection.
    """
    try:
        os.makedirs("uploads/voice_notes", exist_ok=True)

        # Use player_id for unique naming
        filename = f"{player_name}.wav"
        file_path = os.path.join("uploads/voice_notes", filename)
        #save audio file
        with open(file_path, "wb") as f:
            f.write(await audio.read())

        return {
            "message": f"Voice note saved for player {player_id}",
            "player_id": player_id,
            "player_name": player_name,
            "path": file_path,
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error saving voice note: {e}")
    
#@router.post("/uploadVoiceNote", response_model=UploadAudioFileToDBResponse)

# async def upload_voice_note(audio: UploadFile = File(...), player_id : str = Form(...)):
#     """
#     Receives a player's voice note and saves it for later speaker recognition.
#     Returns metadata for confirmation.
#     """
#     try:
#         # Read file bytes
#         audio_bytes = await audio.read()

#         # Save file under uploads/voice_notes/<player_id>.wav
#         import os
#         os.makedirs("uploads/voice_notes", exist_ok=True)
#         file_path = f"uploads/voice_notes/{player_id}.wav"
#         with open(file_path, "wb") as f:
#             f.write(audio_bytes)

#         # Extract metadata (optional)
#         metadata = extract_audio_metadata(
#             audio_bytes,
#             filename=audio.filename,
#             content_type=audio.content_type,
#         )

#         # Return consistent response model
#         return UploadAudioFileToDBResponse(
#             output=f"Voice note for {player_id} saved successfully.",
#             **metadata,
#         )

#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Voice note upload failed: {e}")
