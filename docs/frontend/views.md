# Views

## LoginView

The login/join page handles:

- Preflight connection check to backend
- Player join form (name, campaign)
- WebSocket connection on successful join
- Localhost restriction for DM (leader)
- QR code generation for LAN players
- Backend URL configuration

## HomeView

Main game dashboard orchestrating all core gameplay components. Manages WebSocket lifecycle and disconnect handling.

### Sub-components

- **HomeHeader** — Session management: export/import UI, campaign management, rulebook/config dialogs, save/download session, player list
- **SessionOverview** — Simple greeting showing the current player name
- **QuestionSection** — LLM chat interface with streaming response display and markdown rendering
- **RecordingSection** — Audio recording controls with voiceprint readiness check
- **AudioUploadSection** — File-based audio upload for batch transcription
- **RightRail** — Sidebar container
  - **JoinLink** — QR code and join URL for LAN players
  - **DiceWidget** — Dice roller (d4, d6, d8, d10, d12, d20, d100)
  - **AbilitiesSection** — Player abilities display/edit, HP management (damage/heal), voiceprint upload, kick controls

## ConfigView

Configuration page for selecting LLM, transcription, and embedding models. Includes danger zone actions: clear chat, delete transcriptions.

## TimelineView

Interactive timeline event viewer with:

- Filter events by type (combat, exploration, dialog, etc.)
- Event detail expansion
- Generate events from transcriptions
- Delete individual events or clear all
- Color-coded event categories

## RulebookView

Interactive rulebook browser with:

- Folder tree navigation
- Markdown content rendering with search highlighting
- Full-text search across rulebook
- Responsive layout

## AboutView

Static about page with project information.
