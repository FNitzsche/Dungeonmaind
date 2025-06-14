from pydantic import BaseModel, Field


class UploadAudioFileToDBResponse(BaseModel):
    output: str = Field(..., description="Text generated or metadata from the audio file")
    filename: str = Field(..., description="Original name of the uploaded file")
    content_type: str = Field(..., description="MIME type of the uploaded file")
    size_bytes: int = Field(..., description="Size of the uploaded file in bytes")


class TranscriptionResponse(BaseModel):
    output: str = Field(..., description="Transcribed text from audio file")
