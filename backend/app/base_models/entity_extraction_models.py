from pydantic import BaseModel, Field


class EntityExtractionRequest(BaseModel):
    text: str = Field(
        ...,
        min_length=1,
        description="Transcription text from which entities are extracted",
    )


class ExtractedEntity(BaseModel):
    text: str
    entity_type: str
    start_character: int | None = None
    end_character: int | None = None


class EntityExtractionResponse(BaseModel):
    temporal_entities: list[ExtractedEntity]
    location_entities: list[ExtractedEntity]