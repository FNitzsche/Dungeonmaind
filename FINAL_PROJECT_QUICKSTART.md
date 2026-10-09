# Final combined project: run and test

This archive already combines the latest uploaded frontend with the Release 3 backend additions. All 2,007 files from the latest uploaded project remain unchanged. Extract into a NEW folder for local testing. For your actual GitHub checkout, use the separate additions-only ZIP and follow RELEASE3_BACKEND_ADDITIONS.md; do not replace the whole shared checkout.

## Docker (recommended if this is your current workflow)
From Dungeonmaind-main/, create backend/.env only if absent. In Windows PowerShell:

    Copy-Item backend/.env.example backend/.env

In Linux/macOS:

    cp backend/.env.example backend/.env

Skip copying if you already have your working .env. Set HF_TOKEN inside backend/.env using your own token and retain your existing configuration. See the original README for WhisperX/model-access prerequisites. Never commit your .env.

Start Docker Desktop, then run from the project root:

    docker compose -f dockerCompose.yml -f dockerCompose.map.yml up --build

For your existing NVIDIA setup, include its existing override before the map override:

    docker compose -f dockerCompose.yml -f dockerCompose.gpu.yml -f dockerCompose.map.yml up --build

The existing README describes GPU prerequisites. The last override selects app.main_with_map:app. Wait for model loading and backend startup; initial setup downloads dependencies and models.

Open frontend http://localhost:5173 and Swagger http://localhost:8000/docs. At frontend login use http://localhost:8000 as the backend address from the same computer. Do not enter the internal Docker hostname backend in a browser on your host computer.

## Local alternative
Use your already working Python 3.12 environment and Ollama/FFmpeg setup. From backend/:

    python -m uvicorn app.main_with_map:app --host 0.0.0.0 --port 8000 --reload

In another terminal, from frontend/, use the Node version required in the original README (22.12+ in the 22.x line, or a newer supported release):

    npm ci
    npm run dev

Do not run two backends on port 8000. Starting app.main:app instead leaves map endpoints unavailable.

## Functional check
1. Log in/create an active player using the existing workflow; the map page requires authentication.
2. Record/upload audio that includes clear relationships, for example: The village is north of Neverwinter. The ruined temple lies inside the forest. The old bridge is near Waterdeep. We travelled from Waterdeep to Neverwinter.
3. Wait until transcription finishes. Open Geographic Map and click Generate Map. Check its location graph and supporting evidence.
4. In Swagger, GET /map and POST /map/generate both return nodes, edges, source_segment_count directly. A missing stored map returns empty arrays.
5. Export a session through the existing workflow. Its folder now includes geographic_map.json.
6. Upload/append new audio; GET /map should be empty until generated again.
7. Import the saved session; GET /map should restore that session's map. Importing an older session without a map returns an empty map.
8. Sample demo mode uses invented frontend data and does not prove that backend extraction works. Test session data mode.

HTTP transcription changes invalidate automatically, but generation remains an explicit action. Deleting any saved campaign/session conservatively clears the active map. Failed transcript/import processing leaves an empty map to avoid old-session results. Full lifecycle behavior and limitations are documented in RELEASE3_BACKEND_ADDITIONS.md.

## Automated backend checks
From backend/, with project dependencies available:

    python -m unittest discover -s tests -p 'test_*map*.py'
    python -m unittest discover -s tests -p 'test_spatial_relation_extractor.py'
    python -m unittest discover -s tests -p 'test_entity_extractor.py'

Expected: 28 + 4 + 15 = 47 passing tests. These were verified against this combined source. They use temporary storage and substitutes for heavyweight audio/session operations; they do not load WhisperX or call live Ollama/ChromaDB.

If using Docker, run the commands through:

    docker compose -f dockerCompose.yml -f dockerCompose.map.yml exec backend python -m unittest discover -s tests -p 'test_*map*.py'

Repeat with the other two filename patterns. Include your GPU compose file if you started with it.

Frontend checks from frontend/ (provided by the team; not run here):

    npm run type-check
    npm run build
    npm run test:unit -- --run

No frontend source changes were made. Full browser/audio/model/Docker verification must run in your local environment.

## Troubleshooting
- /map returns 404: confirm app.main_with_map:app is running; use the map compose override.
- Map page redirects to login: create/join the session first.
- Empty map: confirm transcription is stored, generation completed and the transcript contains recognizable places/explicit relationships.
- Missing HF_TOKEN/model access: follow the existing README's setup; the new mapping layer does not replace those prerequisites.
- Port 8000 occupied: stop the previous backend before starting this one.
- Cannot reach backend: set the frontend backend address to http://localhost:8000 for same-machine use.

For Git integration, preserve teammates' work and stage only the additions listed in RELEASE3_BACKEND_ADDITIONS.md. Use a branch/PR through your team's normal process. There is no need to modify the existing main.py or frontend files.
