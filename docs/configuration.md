# Configuration

## Environment Variables

The application is configured via environment variables in `backend/.env`:

| Variable | Default | Description |
|----------|---------|-------------|
| `HF_TOKEN` | — | HuggingFace token (required for WhisperX) |

## Runtime Configuration (Web UI)

The configuration page provides runtime control over:

### LLM Settings
- **Model** — Ollama model to use (e.g., `llama3.2`, `mistral`, `phi4`)
- **Ollama URL** — Ollama server endpoint (default: `http://localhost:11434`)

### Transcription Settings
- **Model** — WhisperX model size (`base`, `small`, `medium`, `large`, `large-v3`)

### Embedding Settings
- **Model** — Sentence transformer model for embeddings
- **Top-K** — Number of similar documents to retrieve for Q&A context

### Danger Zone
- **Clear Chat History** — Reset all per-player chat histories
- **Delete Transcriptions** — Remove all transcription embeddings from ChromaDB

## Internal Settings (code-level)

Defined in `backend/app/core/config.py`:

| Setting | Default | Description |
|---------|---------|-------------|
| `app_name` | `Dungeon M-AI-nd` | Application name |
| `host` | `0.0.0.0` | Backend bind address |
| `port` | `8000` | Backend port |
| `debug` | `false` | Enable debug mode |
| `entity_extraction_fallback` | `false` | Use LLM fallback for entity extraction |
