from typing import List

from pydantic import BaseModel, Field

class Segment(BaseModel):
    start: float = Field(..., description="Segment start time in seconds")
    end: float = Field(..., description="Segment end time in seconds")
    text: str = Field(..., description="Transcribed text for this segment")


class UploadAudioFileToDBResponse(BaseModel):
    output: str = Field(..., description="Text generated or metadata from the audio file")
    filename: str = Field(..., description="Original name of the uploaded file")
    content_type: str = Field(..., description="MIME type of the uploaded file")
    size_bytes: int = Field(..., description="Size of the uploaded file in bytes")


class TranscriptionResponse(BaseModel):
    output: List[Segment] = Field(
        ...,
        description="List of transcription segments with timestamps and text"
    )
