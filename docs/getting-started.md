# Getting Started

## Prerequisites

- Python 3.12+
- Node.js 22+
- Ollama (with a model like `llama3.2` or `mistral`)
- FFmpeg (for audio processing)
- GPU recommended for WhisperX (CUDA)

## Quick Start

### 1. Clone and set up backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env to set your HuggingFace token (required for WhisperX)
```

### 2. Start Ollama

```bash
# Using Docker
docker compose up ollama -d

# Or directly
ollama pull llama3.2
ollama serve
```

### 3. Start the backend

```bash
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 4. Start the frontend

```bash
cd frontend
npm install
npm run dev
```

### 5. Open the app

Navigate to `http://localhost:5173` in your browser.

## Configuration

All configuration is done through the Settings page in the UI or via environment variables. See the [Configuration](configuration.md) page for details.

## Docker Deployment

```bash
docker compose up --build
```

This starts all three services: frontend (Vite dev server), backend (FastAPI + Uvicorn), and Ollama (LLM).
