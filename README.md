# Dungeon M-AI-nd

Dungeon M-AI-nd is a local AI-assisted application for recording, transcribing, searching, and visualizing **Dungeons & Dragons / Pen & Paper sessions**.

The system records or imports session audio, transcribes it using WhisperX, stores searchable transcript data, and uses local AI components to help players and Dungeon Masters revisit previous sessions.

The current implementation includes an interactive timeline and a geographic relationship graph frontend. Geographic map extraction and API integration are still in progress; the graph can already be explored using an explicitly labeled sample demo. Advanced character management and timeline/map integration remain planned.

---

## Project Goal

Long-running D&D campaigns can contain dozens of sessions and many hours of dialogue. Important information such as NPC conversations, locations, discoveries, quests, and combat events can easily be forgotten.

Dungeon M-AI-nd aims to make this information searchable and easier to revisit.

The general processing pipeline is:

```text
Audio
  ↓
Transcription / Speaker Recognition
  ↓
Embeddings and Storage
  ↓
Event / Entity Extraction
  ↓
Timeline and other Visualizations
  ↓
Local LLM Question Answering
```

The application is designed to run with a local backend and Ollama. The frontend connects to the backend address selected at login, so other players can join over the local network. Setup downloads dependencies and models; the frontend also loads a web font from Google Fonts.

---

## Current Project Status

Dungeon M-AI-nd is an active university group project.

### Release 1 — Entity Extraction Prototype

**Status: Stabilization / improvement**

Current implementation includes prototype extraction of:

* temporal expressions,
* locations,
* spatial information.

Automated tests cover temporal extraction, realistic transcript examples, timeline event detection, grounding, and the timeline API. Extraction quality and broader evaluation remain work in progress.

### Release 2 — Interactive Timeline

**Status: Functional prototype / stabilization**

The timeline currently works end-to-end and supports:

* automatic timeline generation from transcripts,
* timestamps,
* event categories,
* event titles and descriptions,
* speakers,
* detected locations,
* temporal expressions,
* transcript context,
* search,
* category filtering,
* detailed event views.

The main remaining problem is **event detection accuracy**. Real D&D recordings can currently produce false-positive or incorrectly classified events.

### Release 3 — Geographic Mapping I

**Status: Interactive frontend implemented; geographic backend integration pending**

The `/map` page includes a validated API client, Pinia store, and reusable Cytoscape.js graph. It supports directed relationship labels, zoom/pan, Fit to View, selection details, elapsed-session timestamps, and keyboard-accessible location and relationship lists.

The backend in this checkout does not yet register GET `/map` or POST `/map/generate`. Session mode reports unavailable APIs explicitly. `/map?demo=sample` displays invented sample data without map API requests; it still uses the existing player/session authentication guard.

### Release 4 — Geographic Mapping II

**Status: Planned**

Timeline/map integration and a dedicated party journey visualization remain planned.

### Release 5 — Advanced Character Sheet

**Status: Planned beyond existing basic character controls**

Player health and ability controls already exist. The advanced sheet and dynamic inventory remain planned.

### Release 6 — Finalization & Submission

**Status: Not started**

---

## Features

### Existing Core Features

* [x] Browser-based session recording
* [x] Upload of prerecorded audio
* [x] Automatic transcription using WhisperX
* [x] Speaker diarization
* [x] Voiceprint registration and speaker identification
* [x] Local LLM integration using Ollama
* [x] Vector-based transcript storage and retrieval
* [x] Question answering based on session transcripts
* [x] Campaign/session organization
* [x] Campaign import/export
* [x] Player and party management
* [x] Character health and ability management
* [x] Built-in dice roller
* [x] Docker-based startup
* [x] CPU mode
* [x] NVIDIA GPU mode

### Interactive Timeline

* [x] Generate events from stored transcript data
* [x] Chronological event display
* [x] Event timestamps and duration
* [x] Event categories
* [x] Speakers
* [x] Location extraction
* [x] Temporal expression extraction
* [x] Timeline search
* [x] Category filtering
* [x] Detailed transcript context
* [ ] Reliable significant-event detection
* [ ] Improved event classification
* [x] Targeted regression tests and sanitized transcript fixtures
* [ ] Broader evaluation dataset
* [ ] Manual timeline correction/editing

### Geographic Relationship Graph

* [x] `/map` route and session navigation
* [x] Cytoscape.js graph with directed, labeled relationships
* [x] Automatic layout, zoom/pan, and Fit to View
* [x] Node/edge selection, details, and elapsed-session timestamps
* [x] Keyboard-accessible textual lists and responsive layout
* [x] Explicit invented-data demo, isolated from session data and API requests
* [x] Loading, generating, error, and empty states
* [x] Graph conversion, selection, lifecycle, and mode-switching tests
* [ ] Geographic extraction backend and live map API integration

### Planned Features

* [ ] Timeline/map integration
* [ ] Party journey visualization
* [ ] Advanced character sheet
* [ ] Dynamic inventory management

---

## Technology Stack

### Backend

* Python
* FastAPI
* WhisperX
* Pyannote
* SentenceTransformers
* ChromaDB
* LangChain

### AI / LLM

* Ollama
* Local language models
* Embedding-based retrieval

### Frontend

* Vue 3
* TypeScript
* Pinia
* Vue Router
* Vite
* Cytoscape.js
* Vitest / Vue Test Utils / Playwright

### Infrastructure

* Docker
* Docker Compose
* NVIDIA GPU support

---

## Repository Structure

```text
Dungeonmaind/
├── backend/
│   ├── app/
│   ├── data/
│   ├── .env.example
│   ├── requirements.txt
│   └── dockerfile
│
├── frontend/
│   ├── src/                 # Includes TimelineView and MapView
│   ├── e2e/                 # Browser regression tests
│   ├── README.md            # Frontend setup and verification
│   ├── package.json
│   └── dockerfile
│
├── LLM/
│   └── dockerfile
│
├── dockerCompose.yml
├── dockerCompose.gpu.yml
├── CONTRIBUTING.md
└── README.md
```

---

# Running the Project

Docker is the recommended way to run Dungeon M-AI-nd.

## Prerequisites

Install:

* Git
* Docker Desktop / Docker Engine
* Docker Compose
* a Hugging Face account
* a Hugging Face access token

For GPU acceleration you additionally need:

* a supported NVIDIA GPU,
* current NVIDIA drivers,
* Docker configured with NVIDIA GPU access.

The first build can take some time because Docker downloads dependencies and AI models.

---

## 1. Clone the Repository

```bash
git clone https://github.com/jrex51/Dungeonmaind.git
cd Dungeonmaind
```

---

## 2. Configure the Environment

The backend expects a `.env` file.

Copy:

```text
backend/.env.example
```

to:

```text
backend/.env
```

Then add your Hugging Face token:

```env
HF_TOKEN=your_huggingface_token_here
```

Do **not** commit your real `.env` file or token to GitHub.

---

# CPU Mode

## First Build

```bash
docker compose -f dockerCompose.yml up --build
```

## Later Starts

```bash
docker compose -f dockerCompose.yml up
```

## Stop

Press `Ctrl+C`, then:

```bash
docker compose -f dockerCompose.yml down
```

---

# NVIDIA GPU Mode

Before starting Dungeon M-AI-nd, verify that Docker can access the GPU.

For example:

```bash
docker run --rm --gpus all nvidia/cuda:12.6.3-base-ubuntu22.04 nvidia-smi
```

If the GPU is detected successfully:

## First Build

```bash
docker compose -f dockerCompose.yml -f dockerCompose.gpu.yml up --build
```

## Later Starts

```bash
docker compose -f dockerCompose.yml -f dockerCompose.gpu.yml up
```

## Stop

Press `Ctrl+C`, then:

```bash
docker compose -f dockerCompose.yml -f dockerCompose.gpu.yml down
```

The GPU override exposes the available NVIDIA GPU to both:

* the backend,
* Ollama.

The application can still run using the normal CPU configuration when GPU acceleration is unavailable.

---

## Open the Application

After the containers are running:

### Frontend

```text
http://localhost:5173
```

### Backend API Documentation

```text
http://localhost:8000/docs
```

### Ollama

```text
http://localhost:11434
```

---

# Basic Usage

## Join a Session

1. Open the frontend.
2. Connect to the backend.
3. Enter a player name.
4. Join as either a Leader or Player.
5. The Leader can manage the session and connected players.

The Leader role is intended to run on the host machine.

---

## Register Player Voiceprints

Before recording a session, players can record short voice samples.

These samples are used to help associate speakers with transcription segments.

1. Open player management.
2. Record a short sample for each player.
3. Save the voiceprint.
4. Verify that the player is registered.

---

## Record a Session

1. Start recording from the frontend.
2. Grant microphone permission when requested.
3. Play the session normally.
4. Audio segments are sent to the backend while recording continues.
5. WhisperX processes the audio and generates transcription data.
6. Stop recording when the session ends.
7. Wait for final transcription processing to complete.

Prerecorded audio can also be uploaded for processing.

---

## Ask Questions About a Session

The local LLM can answer questions using retrieved transcript data.

Examples:

```text
What happened in the tavern?
```

```text
What did the NPC tell us before we left the city?
```

```text
Where did we find the magical dagger?
```

Answers are generated using the locally stored session data.

---

## Interactive Timeline

After transcription data is available, the application can generate a timeline.

Timeline events can contain:

* title,
* description,
* category,
* start and end timestamps,
* duration,
* speakers,
* locations,
* temporal expressions,
* original transcript segments.

The timeline can be searched and filtered by event category.

> **Current limitation:** event extraction is still under development. Some normal dialogue, combat terminology, planning, or D&D mechanics may be incorrectly detected as significant events.

## Geographic Map

1. Join a session, then choose **Geographic Map** alongside **Timeline**.
2. Session mode loads GET `/map`; **Generate Map** explicitly requests POST `/map/generate`. Generation never runs automatically. These endpoints are pending in the backend in this checkout.
3. Choose **Show sample demo**, or open `/map?demo=sample`, to explore the invented sample network without the map backend. Generation is disabled, and the sample is never stored as session results or sent to the backend. Login still requires the player/session backend.
4. Select a location or relationship to inspect its details. Scroll/pinch to zoom, drag the background to pan, and use **Fit to View** to reset the viewport. The textual lists provide the same selection controls for keyboard users.
5. Use **Clear selection** or press Escape while focus is within the map component to deselect. **Use session data** exits the demo and reloads the API.

The graph is schematic: positions do not encode geographic direction, distance, or real-world coordinates. It draws only the relationships supplied in `MapData`. Missing endpoints are reported, and those relationships remain available in the textual list.

See the [map README](frontend/src/views/MapView/README.md) for the provisional contract and detailed manual checks.

## Local Frontend Development and Tests

Use Node.js 22.12 or newer in the 22.x line, or a newer supported Node release, with npm. From the repository root:

```sh
cd frontend
npm ci
npm run dev
```

The frontend normally opens at `http://localhost:5173`. Select the browser-accessible backend address at login (default `http://localhost:8000`). See the [frontend README](frontend/README.md) for LAN startup and test configuration.

Run frontend verification from `frontend/`:

```sh
npm run type-check
npm run build
npm run test:unit -- --run

# Map browser regression: authentication and map responses are mocked.
npx playwright install chromium --only-shell
npm run test:e2e -- e2e/map.spec.ts --project=chromium --reporter=list
```

Backend tests are in `backend/tests/` and use both unittest-style and pytest-style tests. With the backend dependencies installed in your Python environment, install the development test runner and run from `backend/`:

```sh
python -m pip install pytest
python -m pytest tests
```

Tests provide targeted regression coverage; passing them does not establish extraction accuracy on an entire campaign or verify Docker/GPU startup.

---

# Development Workflow

Development is organized using:

* GitHub Issues,
* GitHub Milestones,
* GitHub Projects,
* weekly sprints,
* feature/fix branches,
* Pull Requests,
* code review.

The `main` branch is protected.

Do **not** develop directly on `main`.

All development work should normally follow:

```text
Issue
  ↓
Branch
  ↓
Implementation
  ↓
Pull Request
  ↓
Review
  ↓
Squash Merge
  ↓
main
```

For the complete team workflow, see:

[`CONTRIBUTING.md`](CONTRIBUTING.md)

---

## Branch Examples

```text
feature/event-detection
feature/timeline-editing
fix/item-false-positives
test/timeline-regression
docs/update-readme
refactor/timeline-generator
```

Branches should describe the work being performed rather than the person working on it.

---

# Project Management

The project is divided into six releases. The dates below are planning targets, not evidence that a release has shipped; implementation status is described above.

| Release   | Goal                        | Deadline          |
| --------- | --------------------------- | ----------------- |
| Release 1 | Entity Extraction Prototype | 14 June 2026      |
| Release 2 | Interactive Timeline        | 31 July 2026      |
| Release 3 | Geographic Mapping I        | 30 September 2026 |
| Release 4 | Geographic Mapping II       | 30 November 2026  |
| Release 5 | Advanced Character Sheet    | 31 January 2027   |
| Release 6 | Finalization & Submission   | 31 March 2027     |

Tasks are tracked using GitHub Issues and organized using the **DungeonMAInd Development** project board.

---

# Known Limitations

Current known areas requiring improvement include:

* false-positive timeline events,
* inaccurate event classification,
* limited contextual understanding during event detection,
* prototype-level location extraction,
* prototype-level temporal extraction,
* targeted automated coverage without a comprehensive campaign evaluation dataset,
* geographic map backend/API integration still pending,
* no real-world coordinates, geographic scale, or timeline/map synchronization in the graph,
* session/campaign isolation in parts of the timeline pipeline.

These should be tracked through GitHub Issues rather than fixed directly without an associated task.

---

# Documentation

Project documentation will be maintained alongside the source code.

Relevant documentation includes:

* this README,
* [frontend setup and verification](frontend/README.md),
* [geographic map contract and manual checks](frontend/src/views/MapView/README.md),
* contribution guidelines,
* release documentation,
* sprint meeting documentation,
* API documentation for newly introduced APIs,
* the final user manual.

---

# Contributing

Team members should read [`CONTRIBUTING.md`](CONTRIBUTING.md) before starting development.

In particular:

* do not push directly to `main`,
* work from a GitHub Issue,
* use a task-specific branch,
* link Pull Requests to their Issues,
* test changes before requesting review,
* require at least one teammate approval,
* use squash merging.

---

# License

See [`LICENSE`](LICENSE) for license information.
