# Architecture

## System Context Diagram

```mermaid
C4Context
  title System Context — Dungeon M-AI-nd

  Person(dm, "Dungeon Master", "Runs the session from their browser")
  Person(player, "Player", "Joins via LAN, manages their character")

  System_Boundary(app, "Dungeon M-AI-nd") {
    System(frontend, "Vue 3 Frontend", "Single-page application served by Vite dev server / Nginx")
    System(backend, "FastAPI Backend", "REST + WebSocket API, business logic, data layer")
  }

  System_Ext(ollama, "Ollama", "Local LLM server (llama3.2, mistral, etc.)")
  System_Ext(whisperx, "WhisperX", "Local ASR with speaker diarization")
  System_Ext(chromadb, "ChromaDB", "Vector database for embeddings")

  Rel(dm, frontend, "Uses")
  Rel(player, frontend, "Uses (LAN)")
  Rel(frontend, backend, "HTTP / WebSocket", "REST + WS")
  Rel(backend, ollama, "HTTP", "LLM inference")
  Rel(backend, whisperx, "Subprocess", "Audio transcription")
  Rel(backend, chromadb, "HTTP", "Vector storage & search")

  UpdateLayoutConfig($c4ShapeInRow="4", $c4BoundaryInRow="2")
```

## Container Diagram

```mermaid
C4Container
  title Container — Backend decomposition

  Person(dm, "Dungeon Master")

  System_Boundary(be, "FastAPI Backend") {
    Container(routers, "Routers", "FastAPI", "HTTP request handlers, input validation via Pydantic")
    Container(domain, "Domain Models", "Python dataclasses", "Game entities: Player, Group, TimelineEvent")
    Container(mappers, "Mappers", "Python module", "Domain → Pydantic schema conversion")
    Container(core, "Core Services", "Python", "Config, WebSocket presence bus, chat history")
    Container(functions, "Functions", "Python", "Business logic: embedding, LLM, audio, export")
    ContainerDb(db, "SingleGroupStore", "In-memory", "Current session players & state")
    ContainerDb(tl, "TimelineStore", "In-memory", "Timeline events cache")
  }

  System_Ext(fe, "Vue 3 Frontend")
  System_Ext(ollama, "Ollama")
  System_Ext(whisperx, "WhisperX")
  System_Ext(chroma, "ChromaDB")

  Rel(dm, fe, "Uses")
  Rel(fe, routers, "HTTP / WS")
  Rel(routers, domain, "Uses")
  Rel(domain, mappers, "Serialises via")
  Rel(routers, core, "Uses")
  Rel(routers, functions, "Calls")
  Rel(functions, ollama, "HTTP")
  Rel(functions, whisperx, "Subprocess")
  Rel(functions, chroma, "HTTP")
  Rel(domain, db, "Reads/Writes")
  Rel(domain, tl, "Reads/Writes")
```

## Layer Architecture

```mermaid
graph TB
  subgraph Frontend["Frontend (Vue 3 + TypeScript)"]
    direction TB
    F_Views["Views<br/><small>LoginView, HomeView, ConfigView, TimelineView, RulebookView</small>"]
    F_Stores["Pinia Stores<br/><small>session, timeline, recorder, backendConfig</small>"]
    F_API["API Layer<br/><small>playersAPI, timelineAPI, backendConfigAPI</small>"]
    F_Router["Vue Router<br/><small>with auth guard</small>"]
    F_Views --> F_Stores
    F_Stores --> F_API
    F_Views --> F_Router
  end

  subgraph Backend["Backend (FastAPI)"]
    direction TB
    B_Routers["Routers<br/><small>REST endpoints + WebSocket handlers</small>"]
    B_Domain["Domain Models<br/><small>Player, Group, TimelineEvent (dataclasses)</small>"]
    B_Mappers["Mappers<br/><small>Domain → Pydantic schema conversion</small>"]
    B_Core["Core Services<br/><small>Config, PresenceBus, ChatStore</small>"]
    B_Functions["Functions<br/><small>Embedding, LLM, Audio, Export/Import</small>"]
    B_Routers --> B_Domain
    B_Routers --> B_Core
    B_Routers --> B_Functions
    B_Domain --> B_Mappers
  end

  subgraph External["External Dependencies"]
    direction TB
    E_Ollama["Ollama<br/><small>Local LLM</small>"]
    E_WhisperX["WhisperX<br/><small>ASR + Diarization</small>"]
    E_ChromaDB["ChromaDB<br/><small>Vector Store</small>"]
  end

  F_API <==>|"HTTP / WebSocket<br/>localhost:8000"| B_Routers
  B_Functions --> E_Ollama
  B_Functions --> E_WhisperX
  B_Functions --> E_ChromaDB

  classDef frontend fill:#7c3aed,color:#fff,stroke:#5b21b6
  classDef backend fill:#059669,color:#fff,stroke:#047857
  classDef external fill:#d97706,color:#fff,stroke:#b45309
  class F1,F_Stores,F_API,F_Router frontend
  class B_Routers,B_Domain,B_Mappers,B_Core,B_Functions backend
  class E_Ollama,E_WhisperX,E_ChromaDB external
```

## Key Data Flows

=== "Transcription Pipeline"

    ```mermaid
    sequenceDiagram
      participant F as Frontend
      participant B as Backend
      participant W as WhisperX
      participant C as ChromaDB
      participant O as Ollama

      F->>B: Upload audio (WAV/WebM)
      B->>W: Transcribe + diarize
      W-->>B: Transcript with speaker labels
      B->>B: Match speakers to voiceprints
      B->>C: Store transcription embeddings
      B->>O: Extract timeline events
      O-->>B: Structured event data
      B->>F: Return transcription + events
    ```

=== "Q&A Pipeline"

    ```mermaid
    sequenceDiagram
      participant F as Frontend
      participant B as Backend
      participant C as ChromaDB
      participant O as Ollama

      F->>B: POST question
      B->>C: Semantic search (top-K)
      C-->>B: Relevant transcript excerpts
      B->>B: Build context + system prompt
      B->>O: Stream LLM inference
      O-->>F: Stream response (SSE)
      F->>F: Render markdown
    ```

=== "WebSocket Flow"

    ```mermaid
    sequenceDiagram
      participant P1 as Player 1 (DM)
      participant WS as Backend WS
      participant P2 as Player 2

      P1->>WS: Connect (player_id)
      Note over WS: Add to presence bus
      WS-->>P1: player_joined (self)
      WS-->>P2: player_joined (P1)
      P2->>WS: Connect (player_id)
      WS-->>P1: player_joined (P2)
      Note over P1,P2: Bidirectional state sync
      P1->>WS: update_player (hp, abilities)
      WS-->>P2: player_updated (P1)
      P1->>WS: disconnect
      WS-->>P2: player_left (P1)
    ```

## Component Tree (Frontend)

```mermaid
graph TB
  App["App.vue<br/><small>Root component</small>"]
  Router["Router"]
  Login["LoginView<br/><small>Auth & join</small>"]
  Home["HomeView<br/><small>Dashboard</small>"]
  Config["ConfigView<br/><small>Model config</small>"]
  Timeline["TimelineView<br/><small>Event timeline</small>"]
  Rulebook["RulebookView<br/><small>SRD browser</small>"]
  About["AboutView"]

  HH["HomeHeader<br/><small>Session mgmt, export/import</small>"]
  SO["SessionOverview"]
  QS["QuestionSection<br/><small>LLM chat</small>"]
  RS["RecordingSection<br/><small>Audio recorder</small>"]
  AUS["AudioUploadSection"]
  RR["RightRail"]
  JL["JoinLink<br/><small>QR code</small>"]
  DW["DiceWidget"]
  AS["AbilitiesSection<br/><small>HP, voiceprint, kick</small>"]

  App --> Router
  Router --> Login
  Router --> Home
  Router --> Config
  Router --> Timeline
  Router --> Rulebook
  Router --> About
  Home --> HH
  Home --> SO
  Home --> QS
  Home --> RS
  Home --> AUS
  Home --> RR
  RR --> JL
  RR --> DW
  RR --> AS

  classDef root fill:#4f46e5,color:#fff,stroke:#3730a3
  classDef view fill:#0891b2,color:#fff,stroke:#0e7490
  classDef comp fill:#7c3aed,color:#fff,stroke:#5b21b6
  class App root
  class Login,Home,Config,Timeline,Rulebook,About view
  class HH,SO,QS,RS,AUS,RR,JL,DW,AS comp
```

## Data Storage

| Store | Technology | Location | Contents | Persistence |
|-------|-----------|----------|----------|-------------|
| **Vector Store** | ChromaDB | `backend/data/chroma_db/` | Embeddings (transcriptions + rulebook) | Disk (SQLite + Parquet) |
| **Session Exports** | JSON files | `backend/data/SavedSessions/` | Player groups + config snapshots | Disk (manual save/load) |
| **Rulebook** | Markdown files | `backend/data/markdowns/` | D&D 5e SRD content | Disk (read-only) |
| **Player State** | In-memory dict | `SingleGroupStore` | Current session players | Memory (lost on restart) |
| **Timeline Events** | In-memory list | `TimelineStore` | Timeline events cache | Memory (lost on restart) |
| **Chat History** | In-memory dict | `ChatStore` | Per-player LLM chat history | Memory (lost on restart) |

## Architecture Decisions

| Decision | Rationale |
|----------|-----------|
| **In-memory stores** | Restart is rare; avoids DB ops for transient game state. Export/import provides persistence on demand. |
| **ChromaDB over PostgreSQL** | Full-text + vector search in one service. No schema migrations needed for unstructured session data. |
| **Ollama subprocess** | Runs alongside the app — no API keys, no cloud dependency, fully local. |
| **WhisperX subprocess** | Local ASR with speaker diarization; no audio data ever leaves the machine. |
| **Python/TypeScript split** | FastAPI for Python ML/AI ecosystem; Vue 3 for reactive, type-safe frontend DX. |
| **Mappers layer** | Decouples internal domain models from API contracts; enables schema evolution without touching business logic. |
