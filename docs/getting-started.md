# Getting Started

## Recommended: Docker

```bash
cp backend/.env.example backend/.env
docker compose up --build
```

Then open `http://localhost:5173`. See [Docker Deployment](docker.md) for details.

## Prerequisites (local install)

- Python 3.12+
- Node.js 22+
- Ollama (with a model like Ministral or Phi)
- FFmpeg (for audio processing)
- GPU recommended for WhisperX (CUDA)

## Local Quick Start (without Docker)

### 1. Clone and set up backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env to set your HuggingFace token if needed for diarization
```

### 2. Start Ollama

```bash
ollama pull hf.co/bartowski/mistralai_Ministral-3-3B-Instruct-2512-GGUF:Q5_K_M
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
