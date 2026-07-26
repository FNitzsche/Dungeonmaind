# API Layer

TypeScript functions for communicating with the backend.

## Players API

Exported functions:

- `joinSession` — POST /players (create player)
- `leaveSession` — DELETE /players/{id}
- `listPlayers` — GET /players
- `updateMaxHp` — PATCH /players/{id}/health/max
- `damagePlayer` — POST /players/{id}/damage
- `healPlayer` — POST /players/{id}/heal
- `patchPlayerAbility` — PATCH /players/{id}
- `kickPlayer` — POST /players/{id}/kick
- `postPlayerVoiceprint` — POST /players/{id}/voiceprint
- `checkPlayerExists` — GET /players/join/check
- `getGroupState` — GET /players

## Timeline API

Exported functions:

- `listEvents` — GET /timeline/events
- `getEvent` — GET /timeline/events/{id}
- `deleteEvent` — DELETE /timeline/events/{id}
- `clearSessionEvents` — DELETE /timeline/events
- `generateEvents` — POST /timeline/generate

## Backend Config API

Exported functions:

- `fetchConfig` — GET /config/getConfig
- `submitConfig` — POST /config/changeConfig
