# Stores (Pinia)

## Session Store

Core player and session state management.

- `currentPlayer` — Currently logged-in player
- `players` — All players in the session
- `backendUrl` — Configurable backend URL (persisted in localStorage)
- WebSocket message handlers for join/leave/update events
- Merge/patch logic for player state updates

## Timeline Store

Timeline event state.

- `events` — Array of timeline events
- `eventsByType` — Computed property grouping events by type
- `loading`, `generating`, `error` — Status flags
- Actions: `fetchEvents`, `generateEvents`, `removeEvent`, `clearEvents`

## Recorder Store

Audio recording state using the MediaRecorder API.

- `recording` — Recording state flag
- `audioChunks` — Accumulated audio data
- Chunk rotation (30-second intervals) for live streaming
- Upload to backend on stop
- `transcriptionStatus` — Polling status after upload
- Timer display

## Backend Config Store

Selected model configuration.

- `selectedLLM` — Ollama model name
- `transcriptionModel` — WhisperX model size
- `embeddingModel` — Sentence transformer model
- `embeddingTopK` — Number of results for semantic search
