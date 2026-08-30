from fastapi import APIRouter

from app.base_models.entity_extraction_models import (
    EntityExtractionRequest,
    EntityExtractionResponse,
)
from app.functions.entity_extraction.entity_extractor import (
    extract_entities,
)


router = APIRouter()


@router.post(
    "/extract",
    response_model=EntityExtractionResponse,
)
async def extract_entities_from_text(
    request: EntityExtractionRequest,
) -> EntityExtractionResponse:
    """
    Prototype endpoint for Release 1.

    Extracts temporal expressions, possible locations and spatial
    relations from transcription text.
    """

    temporal_entities, location_entities = extract_entities(
        request.text
    )

    return EntityExtractionResponse(
        temporal_entities=temporal_entities,
        location_entities=location_entities,
    )