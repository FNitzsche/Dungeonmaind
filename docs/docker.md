# Docker Deployment

## Services

The `docker-compose.yml` defines three services:

| Service | Image | Port | Purpose |
|---------|-------|------|---------|
| `frontend` | Node 22 + Nginx | `5173` | Vue 3 dev server (Vite) |
| `backend` | Python 3.12 | `8000` | FastAPI application with Uvicorn |
| `ollama` | Ollama | `11434` | Local LLM server |

## Usage

```bash
# Build and start all services
docker compose up -d

# Build without cache
docker compose build --no-cache

# View logs
docker compose logs -f

# Stop all services
docker compose down
```

## Volumes

- ChromaDB data persists in `backend/data/chroma_db/`
- Session exports persist in `backend/data/SavedSessions/`
- Rulebook data is mounted read-only from `backend/data/markdowns/`

## Ollama Model Setup

After starting the services, pull your desired model:

```bash
docker compose exec ollama ollama pull llama3.2
```

Then configure the model name in the web UI under Configuration → LLM Settings.
