# Geographic Map

The geographic relationship graph frontend is implemented through issues #50 and #51. It works with the existing `MapData` contract and an explicitly labeled invented-data demo. Geographic extraction and the map API are still pending: the backend in this checkout does not register `GET /map` or `POST /map/generate`.

## Modes and states

- `/map` loads session data with GET `/map`. It never generates automatically.
- **Generate Map** sends one bodyless POST `/map/generate`. Loading/generating disable API actions and the mode switch; overlapping requests are prevented.
- Missing APIs, network errors, and unsupported responses show an explicit error with **Retry loading**. They never trigger a sample fallback.
- `{ "nodes": [], "edges": [], "source_segment_count": 0 }` shows the empty state.
- **Show sample demo** switches to `/map?demo=sample`. Opening this URL directly skips the initial map request. The page labels the data as invented, disables generation, and makes no map API calls in sample mode.
- **Use session data** removes the demo query parameter and loads the backend map again. The fixture never enters the map store or API client.
- **Back to session** returns to `/home`. The existing login guard applies in both modes.

The demo needs no **map** backend. Manual use still requires the player/session backend for login and route authentication. The automated browser regression mocks that authentication check as well as map responses.

## Graph and details

`components/MapGraph.vue` is reusable with a `data: MapData` prop. `components/mapGraph.ts` converts nodes and edges without mutating the input or inferring relationships. Existing IDs, endpoints, relation values, evidence, and timestamps are retained.

- Small networks of up to 12 locations use a circular layout, or a single-column grid when the canvas is narrower than 480px. Larger networks use CoSE.
- Edges have arrowheads and readable relationship labels. Underscores are replaced with spaces for display only.
- Scroll/pinch zooms; dragging the background pans. **Fit to View** fits the network to the canvas.
- Selection is highlighted in the graph and reflected in the accessible list buttons.
- Node details show name, mentions, first seen, and last seen.
- Edge details show source, target, relation, evidence, and timestamp.
- Timestamps use elapsed session seconds formatted as `HH:MM:SS`, including hours beyond 24. They are not clock times.
- **Clear selection**, a background tap, or Escape while focus is within the component deselects.
- The textual lists remain available for keyboard selection and when the canvas cannot render. Evidence is rendered as text.
- Edges referencing missing nodes cannot be drawn; they remain selectable in the relationship list, with a visible notice. No replacement locations are invented.

Graph positions do not encode direction, distance, or real-world coordinates. There is no Google Maps/OpenStreetMap integration or timeline/map synchronization.

The component initializes Cytoscape on mount, rebuilds and clears stale selection on replacement or nested changes to data, observes container resizing, and disconnects its observer and destroys the instance on unmount. Mode changes also remount the graph so sample and session selections do not carry over.

## Provisional API contract

`src/api/mapAPI.ts` isolates the frontend's current assumptions for issues #46 and #49 and validates incoming data. Adapt that boundary when the backend contract is finalized.

Both GET and POST return a direct `MapData` JSON object synchronously; there is no response envelope or job polling. POST has no body or session ID and uses the backend's current session.

| Object | Fields |
| --- | --- |
| MapData | `nodes: MapNode[]`, `edges: MapEdge[]`, `source_segment_count: number` |
| MapNode | `id: string`, `name: string`, `mentions: number`, `first_seen: number`, `last_seen: number` |
| MapEdge | `id: string`, `source: string`, `target: string`, `relation: MapRelation`, `evidence: string`, `timestamp: number` |

Counts are nonnegative integers. Timestamps are finite, nonnegative numeric seconds relative to the session. IDs and source/target references are strings; evidence is plain text.

Supported relation values:

```text
north_of, south_of, east_of, west_of, near,
inside, contains, connected_to, travelled_to
```

No stored map is represented by empty arrays and a zero count. HTTP 404 is reported as API unavailable until the backend specifies different semantics. API URLs use the backend address selected in the session, rather than a hardcoded host.

## Automated checks

Run from `frontend/`:

```sh
npm ci
npm run type-check
npm run build
npm run test:unit -- --run src/views/MapView
npx eslint src/views/MapView e2e/map.spec.ts

npx playwright install chromium --only-shell
npm run test:e2e -- e2e/map.spec.ts --project=chromium --reporter=list
```

Vitest covers the API/store boundary, graph conversion, session-relative time, node/edge selection, empty data, dangling endpoints, escaped evidence, resize/unmount cleanup, reactive data updates, and sample/session switching. Component tests use headless Cytoscape because jsdom has no canvas renderer. Playwright exercises the actual canvas at desktop and mobile widths with mocked authentication and map API responses. These checks do not verify live geographic extraction.

## Manual checks

1. From `frontend/`, run `npm ci` and `npm run dev`. Join a session through the existing login flow.
2. Open `http://localhost:5173/map?demo=sample`. Confirm the invented-data label, counts, and disabled **Generate Map** button. In DevTools Network, confirm there are no backend `/map` or `/map/generate` requests; the player existence check is expected.
3. Select **Willowbrook** in the graph or location list. Confirm 3 mentions, first seen `00:00:10`, and last seen `00:02:00`.
4. Select **Silverwood Forest → north of → Willowbrook**. Confirm source/target, relation, sample evidence, and timestamp `00:00:30`.
5. Test zoom, pan, and **Fit to View**. Clear selection using the button or a background tap. Tab to a list button, press Enter/Space to select, then Escape to deselect.
6. Resize to 390px wide. Confirm a single-column graph, details below it, readable lists, and no horizontal page overflow.
7. Choose **Use session data**. Confirm a GET request and the loading state. With the current missing API, expect an explicit error and no invented results. With a compatible backend, empty arrays should show the empty state and populated data should show the network.
8. With a compatible backend, click **Generate Map** and confirm one bodyless POST, a generating state, and disabled actions until completion. Return to sample mode; no selection from session data should remain.
9. Navigate away and reopen the map. Confirm the graph renders again without duplicate canvases or stale details.
