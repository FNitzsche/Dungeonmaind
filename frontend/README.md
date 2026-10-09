# DungeonMAInd Frontend

Vue 3 / TypeScript frontend for session recording and upload, transcript questions, player controls, the event timeline, and the geographic relationship graph. State uses Pinia, navigation uses Vue Router, and the map uses Cytoscape.js.

See the [project README](../README.md) for Docker CPU/GPU startup and backend configuration, and [CONTRIBUTING.md](../CONTRIBUTING.md) for the team workflow.

## Setup and development

Use Node.js 22.12 or newer in the 22.x line, or a newer supported Node release, with npm. Run these commands from `frontend/`:

```sh
npm ci
npm run dev
```

Vite normally serves the app at `http://localhost:5173`. To expose the development server to other devices on your network:

```sh
npm run dev -- --host
```

Choose the backend address at login. The API client reads it from the session store, which persists `backendUrl` in local storage; the fallback is `http://localhost:8000`. For other devices, use the host's reachable LAN address. A Docker service name such as `backend` is not the browser-facing address. The current client does not read `VITE_BACKEND_URL` as its API base URL.

The normal application requires the backend for session login and authenticated routes. The geographic demo requires no map extraction API, but still uses the existing player/session authentication guard.

## Current feature status

- Session recording/upload, transcript questions, campaign/session controls, player management, basic health/abilities, dice, and rulebook views are present.
- The timeline reads and generates events through the backend and provides search, category filtering, and event details. Extraction accuracy remains under development.
- The geographic graph frontend is implemented. The backend in this checkout does not yet register `GET /map` or `POST /map/generate`, so live geographic extraction is pending.
- Advanced character sheets, dynamic inventory, and timeline/map integration remain planned.

### Geographic map

After joining a session, use **Geographic Map** or navigate to `/map`. Session mode loads existing data and generates only when **Generate Map** is clicked. Loading, generation, error, and empty states remain explicit.

Use **Show sample demo** or `/map?demo=sample` to explore invented sample data. The demo is prominently labeled, disables generation, makes no map API requests, and never writes the fixture to the session map store. An API failure never silently substitutes sample results.

The graph provides directed relationship labels, automatic layout, zoom/pan, Fit to View, selection highlighting, and details. All timestamps show elapsed session time as `HH:MM:SS`. Keyboard-accessible location and relationship buttons select the same details as the canvas; Clear selection and Escape within the component deselect. The graph reflows on narrow screens and destroys old Cytoscape instances when data changes or the component unmounts.

Positions are schematic and do not represent geographic direction, distance, or real-world coordinates. Relationships with missing endpoints remain in the text list with a notice. See the [map README](src/views/MapView/README.md) for the API contract and manual checks.

## Build and verification

```sh
npm run type-check
npm run build
npm run preview
```

`build` runs Vue/TypeScript checking and the Vite production build. `preview` serves the generated `dist/` directory, normally on port 4173.

### Vitest

```sh
# All unit/component tests, once rather than watch mode
npm run test:unit -- --run

# Map API/store, page modes, graph conversion, selection, and lifecycle
npm run test:unit -- --run src/views/MapView

# Watch mode during development
npm run test:unit
```

Vitest uses jsdom. Map component tests use real Cytoscape data and selection events in headless mode; the browser test covers the canvas renderer.

### Playwright

The map browser regression mocks player authentication and map API responses, so it requires no running backend. It covers the sample label, API isolation, selection details, Fit to View, desktop/mobile rendering, empty session results, generation requests, and mode switching.

```sh
# Minimal browser installation for the headless Chromium map regression
npx playwright install chromium --only-shell
npm run test:e2e -- e2e/map.spec.ts --project=chromium --reporter=list

# Install all configured browsers, then run all projects
npx playwright install
npm run test:e2e
```

Playwright starts or reuses the Vite development server on port 5173 locally. With `CI` set, build first: the configuration starts the production preview on port 4173 instead. The map test explicitly runs headless. The configured projects are Chromium, Firefox, and WebKit. Screenshots and reports are generated under `test-results/` and `playwright-report/`; these are local artifacts.

### Lint and formatting

```sh
# Check the map sources and browser regression without changing files
npx eslint src/views/MapView e2e/map.spec.ts

# Repository scripts that modify files
npm run lint
npm run format
```

`lint` includes `--fix`; `format` runs Prettier across `src/`.

## Source layout

```text
src/
├── api/                    # Backend clients, including mapAPI.ts
├── config/config.ts        # Dynamic backend address and endpoint paths
├── fixtures/mapSample.ts   # Invented, frontend-only map demo
├── router/index.ts         # Routes and session authentication guard
├── stores/                 # Pinia session, map, and timeline state
└── views/
    ├── HomeView/
    ├── TimelineView/
    └── MapView/
        ├── MapView.vue
        ├── MapView.test.ts
        ├── README.md
        └── components/     # MapGraph.vue, conversion/time helpers, and tests
e2e/map.spec.ts              # Backend-independent map browser regression
```

For editor support, use the Vue language tooling for `.vue` files. The project uses `vue-tsc` rather than plain `tsc` for component type checking.
