# Changelog

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
