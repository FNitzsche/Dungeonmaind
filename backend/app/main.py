"""Application entry point for the Dungeonmaind backend.

Creates and configures the FastAPI application, registers all routers,
and handles startup/shutdown lifecycle for ChromaDB embedding.
"""

import asyncio
import sys

# On windows its possible to run into race conditions when using asyncio.
# Setting the EventLoopPolicy here will prevent async race conditions.
if sys.platform.startswith('win'):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from uvicorn import run

from app.api.routers import (
    config_router,
    export_import_session,
    health,
    llm,
    players,
    process_audio_data,
    root,
    rulebook_markdown,
    timeline,
    ws_players,
)
from app.core.config import settings
from app.functions.embedding.embedding_model import (
    delete_chromadb,
    delete_transcription_embeddings,
    embedd_rulebook,
    has_rulebook_embeddings,
    read_text_files,
)

# List of available api endpoints
all_routers = [
    (root.router, '', ['root']),
    (llm.router, '/llm', ['llm']),
    (process_audio_data.router, '/processAudioData', ['processAudioData']),
    (config_router.router, '/config', ['config']),
    (health.router, '/health', ['health']),
    (players.router, '/players', ['players']),
    (ws_players.router, '/ws', ['ws']),
    (rulebook_markdown.router, '/rulebook', ['rulebook']),
    (export_import_session.router, '/exportImport', ['exportImport']),
    (timeline.router, '/timeline', ['timeline']),
]

# 192.168.x.x und beliebige localhost-Ports zulassen
LAN_REGEX = (
    r'^https?://('  # http:// oder https://
    r'192\.168\.\d{1,3}\.\d{1,3}'  # 192.168.*.*
    r'|10\.d{1,3}\.\d{1,3}\.\d{1,3}'  # 10.*.*.*
    r'|172\.(?:1[6-9]|2\d|3[0-1])\.\d{1,3}\.\d{1,3}'  # 172.16-31.*.*
    r'|localhost'  # localhost
    r'|127\.0\.0\.1'  # 127.0.0.1
    r')(?::\d+)?$'  # optional :Port
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context manager.

    On startup, deletes old ChromaDB temporary folders and re-embeds the
    rulebook if no rulebook embeddings exist. On shutdown, cleans up
    temporary ChromaDB folders.

    Args:
        app: The FastAPI application instance.
    """
    # Startup logic
    logging.info('Server starting: deleting old ChromaDB and re-embedding rulebook...')
    # Check if this deletes everything. Should just delete the tmp folders and for the main db just delete transcriptions
    delete_chromadb(True, False)

    # Rulebook embedding
    # Here check first if the rulebook embeddings are still present in the main db. If not for some reason we add them again. This will also happen
    # on the very first start up of the application
    if settings.run_startup_embedding_maintenance:
        try:
            if not has_rulebook_embeddings():
                texts, txt_paths = read_text_files()
                embedd_rulebook(texts, txt_paths)
                logging.info('Rulebook successfully embedded.')
                print('Rulebook successfully embedded.')
            delete_transcription_embeddings()
        except Exception as e:
            logging.warning(
                'Startup embedding maintenance skipped because the embedding model or '
                'ChromaDB was unavailable: %s',
                e,
            )
            print(f'Warning: Startup embedding maintenance skipped: {e}')
    else:
        logging.info('Startup embedding maintenance disabled.')

    # Save original chroma_db path for shutdown
    chroma_db_path = settings.chroma_db_path

    try:
        yield  # Server running
    finally:
        # Shutdown logic
        # Keep the main db, just delete the tmp bases
        delete_chromadb(True, True, chroma_db_path)
        logging.info('Server Dungeonmaind shutting down...')


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Sets up logging, CORS middleware, and registers all API routers.

    Returns:
        The configured FastAPI application instance.
    """

    # Configure root logger
    logging.basicConfig(
        level=logging.DEBUG if settings.debug else logging.INFO,
        format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
    )
    application = FastAPI(
        title=settings.app_name, debug=settings.debug, version='1.0.0', lifespan=lifespan
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origin_regex=LAN_REGEX,
        allow_credentials=True,
        allow_methods=['*'],
        allow_headers=['*'],
    )

    # Register all routers
    for router, prefix, tags in all_routers:
        application.include_router(router, prefix=prefix, tags=tags)

    return application


app = create_app()

if __name__ == '__main__':
    run(
        app,
        host=settings.host,
        port=settings.port,
        ws='websockets',
        ws_ping_interval=10,
        ws_ping_timeout=10,
        reload=settings.debug,
        log_config=None,
    )
