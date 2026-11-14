# Changelog

## v0.4.0 — unreleased (Release 4, in progress)

### Overview

Release 4 continues the Geographic Mapping feature. This first part makes a session's
transcript, timeline and map part of a saved session, so they survive saving, loading
and a backend restart.

### Added

- **Session files** (`backend/app/functions/export_import/session_files.py`)
  - A saved session folder now also contains `transcript.json`, `timeline.json` and `map.json`
  - `transcript.json` holds `start`, `end`, `text` and `speaker` for each transcribed segment
  - `timeline.json` holds the timeline events; `map.json` holds the map locations and edges
  - Sessions saved before v0.4 still load; the missing files count as empty

- **Transcript store** (`backend/app/domain/transcript_store.py`)
  - In-memory, per-session list of transcribed segments, filled during transcription

- **Session re-keying** (`timeline_store.py`, `map_store.py`, `transcript_store.py`)
  - `rename_session` moves a session's data from the `unsaved` key to `campaign/session`
    when it is saved, so the timeline and map no longer look empty after saving

- **Backend tests** (`backend/tests/`, run with `python -m pytest tests/ -v`)
  - `test_session_files.py`: session files round trip, all-or-nothing save, older saves,
    malformed files, re-keying
  - `test_export_import_router.py`: export, import and campaign listing over HTTP
  - `test_timeline_router.py`, `test_process_audio_router.py`: timeline and audio upload
    endpoints over HTTP
  - `test_recording_to_saved_session.py`: end-to-end flow from audio upload to timeline, map,
    save, restart and load, with the speech models and the LLM replaced by fakes
  - `test_event_extraction_llm.py`: event extraction with a faked Ollama reply
  - `test_session_stores.py`: timeline, transcript and map stores
  - `test_known_bugs.py`: expected-failure tests for open bugs B1, B3 and B9 of the roadmap

- **Frontend tests**
  - Unit tests (Vitest, `npm run test:unit -- --run`) for the session key, the map and timeline
    API clients, the map, timeline and session stores, and `mapFromTimeline`
  - Browser test (Playwright, `npm run test:e2e`) for the timeline and map journey against a
    mocked backend: `frontend/e2e/timeline-map.spec.ts`

### Added (API)

- `GET /session/current`: key and save state of the session the backend is running. Clients
  send this key with every timeline, map, transcription and question request
- `POST /session/new`: start a new, empty session; the previous one keeps its data
- `POST /llm/run` accepts an optional `session_id`; answers only use that session's transcript
- Saved session files carry a `session_uid`

### Changed

- `POST /exportImport/export`
  - Accepts an optional `source_session_id` (the key the transcript, timeline and map are
    currently stored under; defaults to the active session)
  - The save is all-or-nothing: everything is written to a hidden staging folder and moved
    into place only when every part succeeded. A failed save leaves an older save untouched
    and returns an error
- `POST /exportImport/import` validates the three session files before changing anything,
  then loads them under the `campaign/session` key
- `GET /exportImport/getCampaigns` and `getSessions` ignore hidden folders
- `frontend/src/views/HomeView/HomeHeader.vue` sends the current session key when saving
- `.github/workflows/ci.yml` runs the frontend unit tests (Vitest) again
- Formatting only: `process_audio_data.py`, `timeline_store.py` and `transcribe_audio.py`
  now pass `ruff format --check`

### Fixed

- **Sessions no longer share data.** A new game showed the transcript, timeline and map of
  earlier games, for two reasons that are both fixed:
  - Every unsaved game used the same session key (`unsaved`), so their events, map and
    transcript were appended to one shared in-memory bucket. The backend now owns one active
    session with a unique key (`draft-<random>` until saved, `campaign/session` afterwards).
    A new key is created when the backend starts, when a new leader joins and when a saved
    session is loaded. The legacy key `unsaved` now means "the active session"
  - Transcript chunks in ChromaDB carried no session (`session_id: 'none'`), so "Generate
    Events" and the question box read the recordings of every game. Chunks are now tagged with
    a permanent session uid, and `POST /timeline/generate`, `embedding_search` and
    `get_all_transcription_documents` are restricted to one session
  - No stored data is deleted. Untagged chunks from older versions stay in the database and
    are simply never matched. When a session saved by an older version is loaded, the untagged
    chunks in its own database copy are assigned to it
- The frontend takes its session key from the backend (`GET /session/current`) instead of
  computing `unsaved`, and the timeline and map stores drop their data as soon as the session
  changes, so a previous session is never shown
- `TimelineEvent.timestamp` defaulted to an empty string, which made `GET /timeline/events`
  fail with a server error for any event created without a timestamp. It now defaults to `0.0`

### Technical Notes

- Timeline, map and transcript are still held in memory while a session is running; they
  are written to disk when the session is saved.
- Segment times in `transcript.json` are relative to the uploaded audio chunk, as produced
  by transcription today. A session-wide clock is planned for a later part of this release.

## v0.0.1 — 2026-07-09

### Overview

Dungeon M-AI-nd is a locally running, AI-assisted web application for Dungeons & Dragons
players and Dungeon Masters. It records sessions via browser audio, transcribes speech
using WhisperX, stores transcriptions in a vector database (ChromaDB), and enables
semantic Q&A via a local LLM (Ollama). All processing runs locally — no cloud services.

This release introduces the **Interactive Timeline**, the core feature for Release 2,
which extracts significant events from transcribed session audio and displays them on
a visual timeline in the frontend.

### Added

- **Timeline event data model** (`backend/app/domain/models.py`)
  - `TimelineEventType` enum: combat, discovery, dialogue, travel, rest, quest, other
  - `TimelineEvent` dataclass with full serialization (`to_dict` / `from_dict`)
  - Fixed missing `@dataclass` decorator on `Group` class (resolved `AttributeError`)

- **Pydantic API schemas** (`backend/app/base_models/timeline_base_models.py`)
  - `TimelineEventOut`, `TimelineEventListResponse`, `TimelineGenerateRequest/Response`, `TimelineDeleteResponse`

- **In-memory timeline store** (`backend/app/domain/timeline_store.py`)
  - Async thread-safe CRUD: add, list, get, delete events
  - Session-scoped event storage (in-memory; not persisted across restarts)

- **Domain-to-API mapper** (`backend/app/api/mappers/timeline_mapper.py`)
  - Converts domain `TimelineEvent` to Pydantic `TimelineEventOut`

- **LLM-based event extraction** (`backend/app/functions/llm/event_extractor.py`)
  - System prompt for extracting D&D events from transcribed dialogue
  - Single-chunk and batch extraction via Ollama
  - Robust JSON parsing from LLM output with fallback handling
  - Automatic attachment of temporal and location entities

- **Timeline REST API** (`backend/app/api/routers/timeline.py`)
  - `GET /timeline/events` — list events for a session
  - `GET /timeline/events/{event_id}` — get single event
  - `DELETE /timeline/events/{event_id}` — delete an event
  - `DELETE /timeline/events` — clear all events for a session
  - `POST /timeline/generate` — trigger LLM extraction from transcriptions

- **Auto-generation on transcription** (`backend/app/functions/process_audio_data/transcribe_audio.py`)
  - After transcription and embedding, automatically calls `extract_events_from_transcriptions`
  - Graceful diarization model fallback when `HF_TOKEN` is not set
  - Patched `lightning_fabric.cloud_io._load` for PyTorch 2.6+ `weights_only` compatibility

- **Frontend timeline API client** (`frontend/src/api/timelineAPI.ts`)
  - TypeScript interfaces and fetch functions for all timeline endpoints

- **Frontend Pinia store** (`frontend/src/stores/timeline.ts`)
  - State: events, loading, generating, error
  - Computed: `eventCount`, `eventsByType` (grouped for filter display)
  - Actions: fetch, generate, remove, clear

- **Interactive timeline UI** (`frontend/src/views/TimelineView.vue`)
  - Vertical timeline with colored event cards and type badges
  - Filter bar to show/hide event types
  - Modal detail view for individual events
  - Generate Events and Clear All buttons
  - Loading, empty, and error states

- **Timeline route and navigation** (`frontend/src/router/index.ts`, `frontend/src/views/HomeView/HomeHeader.vue`)
  - `/timeline` route with authentication guard
  - Timeline button in the home header

- **Auto-generated code documentation site** (`mkdocs.yml`, `docs/`)
  - MkDocs site with Material theme, dark/light mode, and Mermaid diagrams
  - Auto-generated backend API reference from Google-style docstrings (via mkdocstrings)
  - JSDoc-style docstrings for all frontend TypeScript/Vue modules
  - Architecture page with C4 system diagrams, sequence diagrams, and component trees
  - Run locally with `mkdocs serve` from the project root

- **Project documentation and CI/CD**
  - `README.md`: Added Quick Start (end-to-end run guide for manual and Docker setups)
  - `CHANGELOG.md`: This file
  - `pyproject.toml`: ruff configuration for Python linting and formatting
  - `.pre-commit-config.yaml`: Pre-commit hooks for ruff, ESLint, Prettier, and vue-tsc
  - `.github/workflows/ci.yml`: GitHub Actions workflow for automated checks on push/PR
  - `.editorconfig`: Cross-editor formatting standards (2-space indent, LF, UTF-8)

### Changed

- `backend/app/main.py` — Registered timeline router at `/timeline` prefix
- `frontend/src/config/config.ts` — Added `TIMELINE_EVENTS` and `TIMELINE_GENERATE` endpoints

### Technical Notes

- **Storage**: Timeline events are stored in-memory only. Events are lost on server restart.
  Database persistence is planned for a future release.
- **LLM dependency**: Event extraction requires Ollama running with the Ministral-3B model.
  If Ollama is unavailable, the extractor returns an empty list.
- **Speaker diarization**: Optional. Requires a HuggingFace token (`HF_TOKEN` in `.env`)
  and acceptance of pyannote/speaker-diarization-3.1 terms.
- **PyTorch 2.6+**: The `lightning_fabric` checkpoint loader is patched to use
  `weights_only=False` for compatibility with pyannote checkpoint files.
