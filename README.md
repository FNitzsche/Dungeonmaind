# Dungeon M-AI-nd

> Record yourself, transcribe, and revisit your **Dungeons & Dragons** sessions, all of these done locally, privately, and with AI-assistance.

**Dungeon M-AI-nd** is a locally running software system designed to help Dungeons & Dragons players and Dungeon Masters record their sessions, automatically transcribe spoken dialogue, and later search or query past events using a local large language model (LLM).

All processing is performed locally. No audio, transcripts, or campaign data are sent to external cloud services.

---

## Project Goal

> DnD campaigns often span many sessions, making it difficult to remember details from past campaigns.

Dungeon M-AI-nd addresses this problem by:

1. Recording spoken audio during a session
2. Transcribing it automatically
3. Making the content searchable and queryable

This allows players to retrieve accurate information based on **real session dialogue**, not summaries or manual notes. The goal is to efficiently record your DnD sessions and to make them searchable. Players are be able to ask questions like:

- *"What happened to the magical dagger?"*
- *"What did the NPC say before we left the city?"*

and receive accurate answers based on real transcriptions of their sessions.

---

## Features

- [X] Audio recording via web frontend
- [X] Automatic transcription using WhisperX
- [X] Integration of a local LLM for answering questions
- [X] Clear UI interface for recording and transcription states
- [X] Vector-based storage of transcribed content for retrieval and Q&A
- [X] Campaign export functionality
- [X] Offline mode for laptops/tablets at the game table
- [X] A built-in dice roller is available for quick checks during gameplay.

---

## System Overview

🎙️ Recording → 🧠 Transcription (WhisperX)
→ 🧩 Embedding → 💾 Storage → 🤖 Q&A via LLM

---

## Installation

### Requirements

- Python 3.12
- Git
- Node.js
- ffmpeg (for WhisperX) - very important!
- (Optional but recommended) GPU with CUDA for accelerated transcription by WhisperX and answer-	response times by the llm

### 1. Clone the repository

    ``text 	git clone https://github.com/FNitzsche/Dungeonmaind.git 	cd Dungeonmaind 	``

### 2. Set up the Python environment

    ``text 	pip install -r requirements.txt 	``
For GPU support you need to install CUDA (CUDA Toolkit 12.8.1), cuDNN (cuDNN 9.10.2), ctranslate2 (4.6.0) and:
	```text

    pip uninstall torch torchaudio

    pip install torch==2.8.0 torchaudio==2.8.0 --index-url https://download.pytorch.org/whl/cu128
	```

### 4. Download the latest instance of ffmpeg (url https://www.ffmpeg.org/download.html)

Add it inside the project directory, the corresponding folder must be added to PATH before starting the backend.

### 3. Initialize the frontend

See the README.md file in the 'frontend' folder. (first run ``npm install``, then ``npm run dev``)

---

## Usage

### Start the backend server

1. Ensure all backend dependencies are installed.
2. Start the FastAPI backend (e.g. via uvicorn).
3. The backend must be running before the frontend is opened.

### Start the frontend application

1. Open the provided local URL in a browser of choice.

### Connect to the Backend

1. On the login page, select the backend base URL.
2. Click the connection check. If the check succeeds, the frontend stores the backend URL internally for features to be used later.

### Joining a Session

1. Open the web interface in your browser.
2. Once properly loaded, enter a player name.
3. Join the session as either: Leader (ie Dungeon Master), or Player.
   **Note:**  The Leader role is restricted to localhost connections.
   The Leader can display a QR Code, which other players can scan to join the 			    session on their own devices.
4. Once joined, the party overview becomes visible and updates live.

### Recording Voiceprints for Each Player

1. Wait until all players have joined the session.
2. Navigate to the Abilities/Player Management section.
3. For each player:
   Click Start Recording next to the player’s name.
   Let the player speak for a few seconds (natural speech is sufficient).
   Click Stop Recording.
4. Click Play to verify the recording if needed.
5. Save the recording to store the voiceprint.
6. Once saved, the system marks the player as having a registered voiceprint and the Leader can begin the campaign.

### Recording a Session

1. In the recording section, click Start Recording.
2. When prompted, grant microphone access to the browser.
3. A message confirms that microphone access was granted.
4. A timer appears, indicating that recording is active.
5. Play your Dungeons & Dragons session as usual.
6. While recording is active, the system operates continuously:
   All audio from the selected microphone is captured.
   Audio data is buffered in the browser and periodically segmented.
   Each audio segment is sent incrementally to the backend.
7. The backend already begins processing audio while recording continues, including:
   Speaker diarization and preliminary speaker assignment using the recorded voiceprints.
   Speech-to-text transcription using WhisperX.
8. Recording continues until it is explicitly stopped by the user, thereby allowing long sessions to be handled efficiently without waiting for the entire recording to finish.

### Stopping the Recording

1. Click Stop Recording when the session ends.
2. The recording timer stops and the final audio segment is sent to the backend.
3. A status message soon appears indicating the audio transcription is in progress.
4. The backend eventually completes final transcription, alignment, and speaker labeling.
5. Once final processing is complete, the session is now ready for playback, querying, and export.

### Ask questions

1. Use the web interface to ask questions like:
   ```text
   "What happened in the tavern?"
   ```
2. Optional: enable “show matching rulebook pages”. If enabled, it calls the rulebook search endpoint and shows markdown results with next/previous navigation.
   3.The LLM will respond based on the stored transcriptions which is displayed as a rendered markdown.

### Party Management

1. Real-time visibility of all players in the session, including their health and ability scores.
2. During the campaign, changes can be made to the character abilities. These include
   Adjust ability scores
   Change max HP
   Apply damage/heal
3. Other options include the ability for the Leader to kick members or for the members to leave session manually.

### Session Organization

1. Multi-Campaign Management: Support for creating and organizing sessions into distinct campaigns.
2. Features delete, overwrite, import or export existing sessions within a campaign. The interface automatically prevents exporting or saving until the final transcription is safely finished, preventing data loss.
