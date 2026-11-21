# Docker Deployment

Recommended way to run Dungeon M-AI-nd for demos and releases.

## Services

The `docker-compose.yml` defines three services:

| Service | Image | Port | Purpose |
|---------|-------|------|---------|
| `frontend` | Node (Vite) | `5173` | Vue 3 dev server |
| `backend` | Python 3.12 | `8000` | FastAPI + Uvicorn |
| `ollama` | Ollama | `11434` | Local LLM server |

## Usage

```bash
# One-time: create env file (required by Compose)
cp backend/.env.example backend/.env

# Build and start all services
docker compose up --build

# Detached
docker compose up --build -d

# Build without cache
docker compose build --no-cache

# View logs
docker compose logs -f

# Stop all services
docker compose down
```

Open **http://localhost:5173** after startup.

## Volumes

- `chroma_volume` → `/app/data/chroma_db` (vector store persistence)
- `ollama_volume` → `/root/.ollama` (pulled LLM models)
- Session exports still live under `backend/data/SavedSessions/` via the backend bind mount

## Ollama models

The Ollama image pulls the default Ministral / Phi models during build (see `LLM/run-ollama.sh`). To pull more:

```bash
docker compose exec ollama ollama pull <model-name>
```

Then select the model in the web UI under Configuration → LLM Settings.

## Notes

- Browser clients must use `http://localhost:8000` (published host port), not the Docker service hostname `backend`.
- First backend image build downloads WhisperX and embedding models; later rebuilds are faster with cache.
