# Dungeon M-AI-nd

A locally-running AI-assisted web application for Dungeons & Dragons players. Record your D&D sessions, get automatic transcriptions, search past sessions semantically, and ask questions about your game using a local LLM — all running on your machine.

## Features

- **Audio Recording & Transcription** — Record sessions via browser microphone; transcribe with WhisperX (speaker diarization included)
- **Vector Search** — Store transcriptions in ChromaDB; search across all sessions with semantic similarity
- **LLM-Powered Q&A** — Ask questions about your campaign; answers are grounded in your actual session transcripts
- **Rulebook Integration** — Browse and search the D&D 5e SRD rulebook embedded into the knowledge base
- **Timeline Events** — Automatically extract structured events (combat, exploration, dialog) from transcriptions
- **Entity Extraction** — Identify locations, NPCs, items, and temporal references from session text
- **Player Management** — Real-time player presence via WebSocket; HP tracking, damage/heal, voiceprint linking
- **Export/Import** — Save and restore complete session snapshots (players, settings, vector DB)
- **Dice Rolling** — Built-in dice roller (d4 through d100)

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                    Frontend (Vue 3)                   │
│  Pinia Stores ←→ API Layer ←→ Vue Router ←→ Views   │
└──────────────────────┬──────────────────────────────┘
                       │ HTTP / WebSocket
┌──────────────────────▼──────────────────────────────┐
│                   Backend (FastAPI)                   │
│  Routers → Domain Models → Functions → ChromaDB      │
│                                    → Ollama (LLM)    │
│                                    → WhisperX (ASR)  │
└─────────────────────────────────────────────────────┘
```

The entire application is designed for **local-first** operation. No data leaves your machine. The LLM runs via [Ollama](https://ollama.ai), WhisperX handles transcription locally, and all data is stored in local ChromaDB and filesystem.

## Documentation

The full documentation site is built with [MkDocs](https://www.mkdocs.org) using the [Material theme](https://squidfunk.github.io/mkdocs-material/). It includes auto-generated API reference from docstrings, Mermaid architecture diagrams, and detailed guides.

### View the documentation

```bash
# From the project root
mkdocs serve

# Then open http://localhost:8000 in your browser
```

The documentation covers:
- **Getting Started** — Prerequisites and quick-start guide
- **Architecture** — C4 system diagrams, data flows, component tree, and design decisions
- **Backend API Reference** — Auto-generated docs for all routers, domain models, core services, mappers, and functions (via mkdocstrings)
- **Frontend** — Overview of views, Pinia stores, API layer, and router
- **Configuration** — All environment variables and runtime settings
- **Docker Deployment** — Docker Compose service definitions and usage
