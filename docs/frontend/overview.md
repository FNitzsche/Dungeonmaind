# Frontend Overview

The frontend is a **Vue 3** application built with TypeScript, Pinia for state management, and Vue Router for navigation.

## Tech Stack

- **Framework**: Vue 3 (Composition API + `<script setup>`)
- **Language**: TypeScript
- **State Management**: Pinia
- **Routing**: Vue Router 4
- **Build Tool**: Vite
- **HTTP**: Native `fetch` API
- **Real-time**: WebSocket (native)
- **Markdown Rendering**: `marked` library
- **QR Codes**: `qrcode.vue`
- **Testing**: Vitest + Playwright

## Directory Structure

```
frontend/src/
├── main.ts                 # App entry point
├── App.vue                 # Root component
├── api/                    # Backend API layer
│   ├── backendConfigAPI.ts
│   ├── playersAPI.ts
│   └── timelineAPI.ts
├── assets/                 # CSS and static assets
│   ├── base.css
│   ├── main.css
│   └── styles.css
├── components/             # Shared/reusable components
│   ├── HelloWorld.vue
│   ├── TheWelcome.vue
│   └── icons/
├── config/                 # App configuration
│   └── config.ts
├── router/                 # Vue Router configuration
│   └── index.ts
├── stores/                 # Pinia stores
│   ├── backendConfig.ts
│   ├── recorder.ts
│   ├── session.ts
│   └── timeline.ts
└── views/                  # Page components
    ├── HomeView/           # Main dashboard (9 sub-components)
    ├── AboutView.vue
    ├── ConfigView.vue
    ├── LoginView.vue
    ├── RulebookView.vue
    └── TimelineView.vue
```
