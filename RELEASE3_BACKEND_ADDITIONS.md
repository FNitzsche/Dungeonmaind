# Release 3 backend: issues 46–49 and automatic session integration

## What is included
This is an ADDITIONS-ONLY archive. All 1,994 files in your original uploaded project were verified byte-for-byte unchanged. It contains map models, sample JSON, spatial relation extraction, graph generation, JSON storage, GET /map, POST /map/generate, tests, an optional application entry point and a Docker command override.

This version supersedes the earlier additions ZIP. If you installed the earlier version, replace ONLY files previously supplied by this package with the updated versions. Compare any filename that a teammate has independently added; do not overwrite their work.

## 1. Put the files into your project
1. Prefer working in a separate branch: git switch -c feature/release3-geographic-mapping
2. Extract this ZIP into a temporary directory.
3. Copy its backend/ contents into your existing backend/ folder, preserving directory structure.
4. Copy dockerCompose.map.yml and this instruction file to your project root.
5. Your original main.py, dockerCompose.yml, requirements.txt, audio/session endpoints and frontend files are not replaced.

## 2. Start locally
Use the same Python 3.12 environment, dependencies, .env and running Ollama service as your already working project. No new dependency is required beyond the existing requirements. If your environment is not installed yet, follow the original README and requirements.txt; the original WhisperX/FFmpeg/model-token prerequisites still apply.

Stop the old backend listening on port 8000. From the project root:

    cd backend
    python -m uvicorn app.main_with_map:app --host 0.0.0.0 --port 8000 --reload

The key change is the command's module: app.main_with_map:app. Starting app.main:app instead will NOT enable the new map endpoints or lifecycle hooks. The original frontend can continue running as before.

## 3. Start through Docker instead
From the project root, use the existing base compose file plus the NEW override:

    docker compose -f dockerCompose.yml -f dockerCompose.map.yml up --build

The override only changes the backend startup command; your original compose file is untouched. Do not run the local backend and Docker backend on the same port simultaneously. Stop this Docker setup with:

    docker compose -f dockerCompose.yml -f dockerCompose.map.yml down

Do not add --volumes when stopping if you want to retain your existing volumes. These commands are provided for your environment; Docker and full model startup were not run here.

## 4. Generate and inspect your first map
1. Open http://localhost:8000/docs.
2. Use POST /processAudioData/transcribeAudioFile with an audio recording, or use existing stored transcription data.
3. Use POST /map/generate, then Execute. No request body is needed.
4. Use GET /map, then Execute. It returns the stored map without rerunning generation.

Command-line equivalents:

    curl -X POST http://localhost:8000/map/generate
    curl http://localhost:8000/map

On Windows PowerShell use curl.exe for these examples if curl resolves to a PowerShell alias.

## 5. Automatic lifecycle behavior
| Operation | Map behavior |
| --- | --- |
| Replace transcription | Clears the previous map before transcription processing |
| Append transcription, replace_existing=false | Also clears the old map, because it no longer covers the current transcript |
| Generate map | Builds and atomically saves the current graph |
| GET map | Retrieves saved graph; missing storage returns an empty graph |
| Export session | Existing export runs, then saves geographic_map.json inside that session folder |
| Import session with a valid saved map | Validates the saved map first, clears old active map, performs import, then restores the saved map |
| Import older session without a map | Clears old active map; the imported session has an empty map until generated |
| Import session with corrupt map | Returns 409 before running the original import |
| Rename saved session | Original folder rename moves its saved map together with the other session files |
| Successful campaign/session deletion | Clears active map conservatively; original backend does not track which saved session is currently active |
| Failed deletion | Leaves active map unchanged |

Clearing is automatic; generation is still explicit via POST /map/generate. After uploading/appending audio, generate again when transcription completes. There is no LLM cost or automatic repeated generation on GET.

If transcription/import fails after processing begins, the active map stays empty to avoid showing evidence from the previous data. If map generation fails, the previous map remains intact. Export map-writing failure returns an error; the original export may already have saved other files, so fix the error and retry export.

Map generation, export/import, transcription, rename and deletion requests are serialized in this optional app, preventing these HTTP operations from racing each other. GET remains responsive during generation and can return the prior stored graph. During transcript replacement/import it returns an empty graph until a new/restored map is available.

The active map lives at settings.backend_root_path/data/geographic_map.json. Saved session maps live at settings.backend_root_path/data/SavedSessions/<campaign>/<session>/geographic_map.json.

## 6. Check export/import in Swagger
1. Generate a nonempty map and inspect GET /map.
2. POST /exportImport/export with:

    {"campaign_name": "MyCampaign", "session_name": "Session1"}

The original export prerequisites still apply, including an active player/group.
3. Transcribe another recording: GET /map should now be empty.
4. POST /exportImport/import with the same JSON: GET /map should restore Session1's map.
5. Import a previously saved session without geographic_map.json: GET /map should be empty.
6. Rename Session1 through the existing rename endpoint: the saved map remains with that folder.

## 7. Tests
From backend/, in your project environment:

    python -m unittest discover -s tests -p 'test_*map*.py'
    python -m unittest discover -s tests -p 'test_spatial_relation_extractor.py'
    python -m unittest discover -s tests -p 'test_entity_extractor.py'

Validated here: 28 map/model/API/storage/session tests, 4 spatial extraction tests and 15 existing entity-extraction regression tests: 47 total, all passing. API/session tests use real FastAPI request handling, temporary files and lightweight substitutes for the original heavyweight endpoints. Full app startup, live ChromaDB, actual WhisperX transcription, Ollama and Docker are not verified here.

## 8. Review and commit only these additions
From the project root, inspect git status and git diff first. Stage only these paths:

    git add backend/app/base_models/map_models.py backend/app/api/routers/map.py backend/app/main_with_map.py backend/app/functions/geographic_mapping backend/tests/data/map_sample.json backend/tests/test_map_generator.py backend/tests/test_map_api.py backend/tests/test_map_session_integration.py backend/tests/test_spatial_relation_extractor.py dockerCompose.map.yml RELEASE3_BACKEND_ADDITIONS.md
    git diff --cached --stat
    git commit -m "Add Release 3 geographic map backend and session integration"

Do not use git add . if teammates' unrelated changes are present. Publish the branch through your team's normal process and describe that app.main_with_map or the compose override is required to activate this addition. No original source edit or merge was performed here.

## Contract and extraction details
MapNode: id, name, mentions, first_seen, last_seen.
MapEdge: id, source, target, relation, evidence, timestamp.
MapData: nodes, edges, source_segment_count.
Relations: north_of, south_of, east_of, west_of, near, inside, contains, connected_to, travelled_to.

mentions is a text occurrence count. first_seen and last_seen are the first segment start and last segment end, recording-relative seconds. Edge timestamp is the supporting segment's start. Evidence preserves its sentence text with outer whitespace removed. source_segment_count counts nonempty transcription documents. Node/edge IDs are deterministic for unchanged input; generic place IDs depend on segment ordering. No coordinates or timeline-event IDs are added to the agreed contract.

The English extractor covers simple complete statements such as the four leader examples. It skips negation, questions, hypothetical language, unresolved pronouns and unsupported compound forms. It does not infer relationships from co-occurrence. Named locations normalize articles/spacing/case. Generic caves/villages/temples are scoped per segment to avoid silently merging different places. This limits continuity for generic names and does not resolve aliases or complex narrative. LLM-based relation extraction is not included.

## Runtime integration limits
Hooks are installed on routes of the optional app instance; existing router source files are untouched. They use the project's FastAPI 0.119 route machinery. Startup fails clearly if a required endpoint path is renamed by another teammate, rather than silently losing lifecycle integration. Keep the existing single-worker setup: serialization is process-local. Direct script/database edits or future transcription endpoints bypassing these HTTP routes are not tracked; such integrations should explicitly invalidate the map. Saved map JSON is validated, but externally modifying a saved ChromaDB without regenerating its map is outside these hooks.
