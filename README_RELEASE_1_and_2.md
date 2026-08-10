# Dungeonmaind

This repository contains the implementation of **Release 1** and **Release 2**.

---

# Release 1 – Core D&D Assistant

Release 1 provides the basic functionality required to manage D&D sessions and interact with the game using AI.

## Features

### Player Management

- Create and join a D&D session.
- Support for Leader and Player roles.
- Display active players.
- Leave the session.

### Voiceprint Registration

- Record a short voice sample for each player.
- Store voiceprints for speaker recognition during transcription.

### Audio Processing

- Upload prerecorded audio sessions.
- Record sessions directly using the microphone.
- Automatic transcription using WhisperX.
- Speaker diarization using Pyannote.
- Speaker identification using registered voiceprints.

### AI Question Answering

Players can ask questions about the recorded session, for example:

- Where did the party arrive?
- Who defeated the goblin?
- What happened after entering the cave?
- Where did the party rest?

The system retrieves relevant transcription segments using Retrieval-Augmented Generation (RAG) and generates answers using a local Large Language Model (LLM) running with Ollama.

# Release 2 – Interactive Timeline

Release 2 introduces automatic event extraction and an interactive timeline for reviewing recorded sessions.

## Timeline Generation

The system automatically analyzes transcription segments stored in ChromaDB and groups related events chronologically.

Each timeline event contains:

- Event title
- Event description
- Event category
- Start time
- End time
- Duration
- Speakers
- Locations
- Temporal expressions
- Original transcription segments

---

## Supported Event Categories

The timeline automatically classifies events into:

- Travel
- Combat
- Dialogue
- Discovery
- Rest
- Quest
- Item
- Other

---

## Timeline Features

### Interactive Timeline

The timeline displays events in chronological order together with their timestamps.

### Event Details

Selecting an event opens a detailed view showing:

- Event summary
- Event duration
- Speakers involved
- Locations
- Temporal references
- Original transcript segments

### Timeline Search

Users can search timeline events by:

- Event title
- Description
- Speaker
- Location

### Category Filtering

Timeline events can be filtered using their category.

---

## Automatic Information Extraction

The timeline generation automatically detects:

### Locations

Example:

- Neverwinter
- Tavern
- River
- Old Bridge
- Cave

### Temporal Expressions

Example:

- Two days later
- Before sunset
- This morning
- At midnight

# Technology Stack

## Frontend

- Vue 3
- TypeScript
- Pinia
- Vue Router

## Backend

- FastAPI
- Python

## AI Technologies

- WhisperX (Speech-to-Text)
- Pyannote (Speaker Diarization)
- SentenceTransformers
- ChromaDB
- LangChain
- Ollama

# Running the Project

## Prerequisites

Install:

- Git
- Docker Desktop (WSL2 enabled on Windows)
- Hugging Face account
- Hugging Face Access Token

---

## Clone the Repository

```bash
git clone <repository-url>

cd Dungeonmaind
```

---

## Configure Environment

Before running the project, create a file named `.env` inside the `backend` folder.

Example:

```text
Dungeonmaind_Mevil_Release2/
│
├── backend/
│   ├── .env
│   ├── app/
│   ├── data/
│   └── ...
├── frontend/
└── dockerCompose.yml
```

Add the following line to the `.env` file:

```env
HF_TOKEN=your_huggingface_token_here
```

Replace `your_huggingface_token_here` with your own Hugging Face access token before running the project.

## First-Time Setup

### CPU

```bash
docker compose -f dockerCompose.yml up --build
```

### NVIDIA GPU

First, verify that Docker can access the GPU:

```bash
docker run --rm --gpus all nvidia/cuda:12.6.3-base-ubuntu22.04 nvidia-smi
```

Then build and start with GPU support:

```bash
docker compose -f dockerCompose.yml -f dockerCompose.gpu.yml up --build
```

## Starting the Project Later

After the first successful build, you normally do not need to rebuild.

### CPU

```bash
docker compose -f dockerCompose.yml up
```

### NVIDIA GPU

```bash
docker compose -f dockerCompose.yml -f dockerCompose.gpu.yml up
```

## Stopping the Project

Press `Ctrl + C`, then run:

### CPU

```bash
docker compose -f dockerCompose.yml down
```

### GPU

```bash
docker compose -f dockerCompose.yml -f dockerCompose.gpu.yml down
```



## Open the Application

Frontend

```
http://localhost:5173
```

Backend API

```
http://localhost:8000/docs
```
