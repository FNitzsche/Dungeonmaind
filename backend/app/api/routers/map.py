"""Map routes. Register with prefix='/map' in the existing main app."""
import asyncio
from functools import lru_cache
import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from app.base_models.map_models import MapData
from app.functions.geographic_mapping.map_generator import generate_map_from_embeddings
from app.functions.geographic_mapping.map_store import MapStore

router = APIRouter()
logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_map_store():
    from app.core.config import settings
    return MapStore(Path(settings.backend_root_path) / "data" / "geographic_map.json")


@router.get("", response_model=MapData, summary="Retrieve the stored geographic map")
async def get_map(store: MapStore = Depends(get_map_store)):
    try:
        return await asyncio.to_thread(store.get_map)
    except Exception as error:
        logger.exception("Unable to read geographic map")
        raise HTTPException(status_code=500, detail="Unable to read the stored map") from error


def _generate_and_store(store):
    return store.replace_map(generate_map_from_embeddings())


@router.post("/generate", response_model=MapData, summary="Generate and store a geographic map")
async def generate_map(store: MapStore = Depends(get_map_store)):
    try:
        return await asyncio.to_thread(_generate_and_store, store)
    except Exception as error:
        logger.exception("Unable to generate geographic map")
        raise HTTPException(status_code=500, detail="Map generation failed; previous map retained") from error
