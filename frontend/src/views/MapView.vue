<script setup lang="ts">
/**
 * MapView – displays a schematic campaign map built from session places.
 * Loads backend map data when available, otherwise derives nodes from timeline events.
 */
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useMapStore } from '@/stores/map'
import { useSessionStore } from '@/stores/session'
import { useTimelineStore } from '@/stores/timeline'
import type { MapEdge, MapEdgeType } from '@/api/mapAPI'

const router = useRouter()
const route = useRoute()
const mapStore = useMapStore()
const timelineStore = useTimelineStore()
const sessionStore = useSessionStore()

const svgRef = ref<SVGSVGElement | null>(null)
const selectedEdgeKey = ref<string | null>(null)

const zoom = ref(1)
const pan = ref({ x: 0, y: 0 })
const isPanning = ref(false)
const panStart = ref({ x: 0, y: 0, panX: 0, panY: 0 })

const edgeLabels: Record<MapEdgeType, string> = {
  traveled: 'Traveled',
  near: 'Near',
  north_of: 'North of',
  inside: 'Inside',
  other: 'Linked',
}

const edgeColors: Record<MapEdgeType, string> = {
  traveled: '#b45309',
  near: '#2f6f8f',
  north_of: '#2e7d4f',
  inside: '#7b4d8e',
  other: '#8a7a4a',
}

/**
 * Sequential "journey" layout: places are laid out in visit order along a
 * serpentine path (left-to-right, then wrapping back), so the eye follows
 * Start → … → End instead of an orderless ring.
 */
const layout = computed(() => {
  const nodes = mapStore.nodes
  const positions = new Map<string, { x: number; y: number }>()
  const count = nodes.length
  if (count === 0) return { positions, width: 800, height: 460 }

  const cols = Math.min(count, count <= 3 ? count : 4)
  const rows = Math.ceil(count / cols)
  const cellW = 250
  const cellH = 200
  const padX = 130
  const padY = 130

  nodes.forEach((node, index) => {
    const row = Math.floor(index / cols)
    const colInRow = index % cols
    const serpCol = row % 2 === 0 ? colInRow : cols - 1 - colInRow
    positions.set(node.id, { x: padX + serpCol * cellW, y: padY + row * cellH })
  })

  return {
    positions,
    width: Math.max(padX * 2 + (cols - 1) * cellW, 520),
    height: Math.max(padY * 2 + (rows - 1) * cellH + 40, 280),
  }
})

const nodePositions = computed(() => layout.value.positions)
const canvasAspect = computed(() => `${layout.value.width} / ${layout.value.height}`)
const viewportTransform = computed(
  () => `translate(${pan.value.x} ${pan.value.y}) scale(${zoom.value})`,
)

const highlightedPlaceId = computed(() => {
  const fromQuery = mapStore.resolvePlaceQuery(
    typeof route.query.place === 'string' ? route.query.place : null,
  )
  return mapStore.selectedPlaceId ?? fromQuery
})

/** Ids of the selected place plus everything directly linked to it. */
const connectedNodeIds = computed(() => {
  const selected = highlightedPlaceId.value
  if (!selected) return null
  const ids = new Set<string>([selected])
  mapStore.edges.forEach((edge) => {
    if (edge.from === selected) ids.add(edge.to)
    if (edge.to === selected) ids.add(edge.from)
  })
  return ids
})

const activeLegend = computed(() => {
  const present = new Set(mapStore.edges.map((edge) => edge.type))
  return (Object.keys(edgeLabels) as MapEdgeType[]).filter((type) => present.has(type))
})

const journeyOrderLine = computed(() => {
  const labels = mapStore.nodes.map((node) => truncateLabel(node.label, 18))
  if (labels.length === 0) return ''
  return `Journey: ${labels.join(' → ')}`
})

const selectedEvents = computed(() => {
  const ids = new Set(mapStore.selectedEventIds)
  return timelineStore.events
    .filter((event) => ids.has(event.id))
    .sort((a, b) => (a.order ?? 0) - (b.order ?? 0))
})

const selectedLinks = computed(() => {
  const selected = highlightedPlaceId.value
  if (!selected) return []
  return mapStore.edges
    .filter((edge) => edge.from === selected || edge.to === selected)
    .map((edge) => {
      const outward = edge.from === selected
      return {
        key: `${edge.from}->${edge.to}:${edge.type}`,
        type: edge.type,
        label: edgeLabels[edge.type] || 'Linked',
        otherId: outward ? edge.to : edge.from,
        otherLabel: nodeLabel(outward ? edge.to : edge.from),
        direction: outward ? 'to' : 'from',
      }
    })
})

const selectedEdge = computed(() => {
  if (!selectedEdgeKey.value) return null
  return (
    mapStore.edges.find((edge, index) => edgeKey(edge, index) === selectedEdgeKey.value) ?? null
  )
})

function edgeKey(edge: MapEdge, index: number): string {
  return `${edge.from}-${edge.to}-${edge.type}-${index}`
}

function nodeLabel(id: string): string {
  return mapStore.nodes.find((node) => node.id === id)?.label ?? id
}

function truncateLabel(label: string, max = 22): string {
  const trimmed = label.trim()
  if (trimmed.length <= max) return trimmed
  return `${trimmed.slice(0, max - 1)}…`
}

function placeIcon(label: string): string {
  const text = label.toLowerCase()
  if (/(forest|woods|grove|thicket)/.test(text)) return '🌲'
  if (/(village|town|shire|city|brook|vale)/.test(text)) return '🏘'
  if (/(sanctum|temple|shrine|church)/.test(text)) return '⚜'
  if (/(cave|mine|dungeon|expanse|crust)/.test(text)) return '⛰'
  if (/(castle|fort|keep|kharzul)/.test(text)) return '🏰'
  return '📍'
}

function nodeDimmed(id: string): boolean {
  const connected = connectedNodeIds.value
  return connected ? !connected.has(id) : false
}

function edgeTouchesSelection(from: string, to: string): boolean {
  const selected = highlightedPlaceId.value
  return selected ? from === selected || to === selected : false
}

function isStart(index: number): boolean {
  return index === 0
}

function isEnd(index: number): boolean {
  return index === mapStore.nodes.length - 1
}

function edgeMidpoint(fromId: string, toId: string): { x: number; y: number } | null {
  const from = nodePositions.value.get(fromId)
  const to = nodePositions.value.get(toId)
  if (!from || !to) return null
  const dx = to.x - from.x
  const dy = to.y - from.y
  const len = Math.hypot(dx, dy) || 1
  const arc = Math.min(70, len * 0.2)
  const cx = (from.x + to.x) / 2 - (dy / len) * arc
  const cy = (from.y + to.y) / 2 + (dx / len) * arc
  // Approximate quadratic midpoint.
  return {
    x: 0.25 * from.x + 0.5 * cx + 0.25 * to.x,
    y: 0.25 * from.y + 0.5 * cy + 0.25 * to.y,
  }
}

function goBack() {
  router.push({ name: 'home' })
}

function goToTimeline() {
  router.push({ name: 'timeline' })
}

async function handleSelectPlace(placeId: string) {
  selectedEdgeKey.value = null
  await mapStore.selectPlace(placeId)
  const node = mapStore.nodes.find((item) => item.id === placeId)
  if (node) {
    router.replace({ name: 'map', query: { place: node.label } })
  }
}

async function handleSelectEdge(edge: MapEdge, index: number) {
  selectedEdgeKey.value = edgeKey(edge, index)
  await handleSelectPlace(edge.to)
}

function clearSelection() {
  selectedEdgeKey.value = null
  mapStore.clearSelection()
  router.replace({ name: 'map', query: {} })
}

function openTimelineEvent(eventId: string) {
  router.push({ name: 'timeline', query: { event: eventId } })
}

function fitToJourney() {
  zoom.value = 1
  pan.value = { x: 0, y: 0 }
}

function onWheel(event: WheelEvent) {
  event.preventDefault()
  const delta = event.deltaY > 0 ? -0.08 : 0.08
  zoom.value = Math.min(2.4, Math.max(0.55, zoom.value + delta))
}

function onPointerDown(event: PointerEvent) {
  if (event.button !== 0) return
  const target = event.target as Element | null
  if (target?.closest('.node-group, .edge-group')) return
  isPanning.value = true
  panStart.value = {
    x: event.clientX,
    y: event.clientY,
    panX: pan.value.x,
    panY: pan.value.y,
  }
  svgRef.value?.setPointerCapture(event.pointerId)
}

function onPointerMove(event: PointerEvent) {
  if (!isPanning.value) return
  pan.value = {
    x: panStart.value.panX + (event.clientX - panStart.value.x),
    y: panStart.value.panY + (event.clientY - panStart.value.y),
  }
}

function onPointerUp(event: PointerEvent) {
  if (!isPanning.value) return
  isPanning.value = false
  svgRef.value?.releasePointerCapture(event.pointerId)
}

async function stepJourney(delta: number) {
  const nodes = mapStore.nodes
  if (nodes.length === 0) return
  const currentId = highlightedPlaceId.value
  let index = currentId ? nodes.findIndex((node) => node.id === currentId) : -1
  if (index < 0) index = delta > 0 ? -1 : 0
  const next = Math.min(nodes.length - 1, Math.max(0, index + delta))
  await handleSelectPlace(nodes[next].id)
}

function onKeydown(event: KeyboardEvent) {
  if (event.key === 'ArrowRight' || event.key === 'ArrowDown') {
    event.preventDefault()
    void stepJourney(1)
  } else if (event.key === 'ArrowLeft' || event.key === 'ArrowUp') {
    event.preventDefault()
    void stepJourney(-1)
  } else if (event.key === 'Escape') {
    clearSelection()
  }
}

function edgePath(fromId: string, toId: string): string {
  const from = nodePositions.value.get(fromId)
  const to = nodePositions.value.get(toId)
  if (!from || !to) return ''
  const dx = to.x - from.x
  const dy = to.y - from.y
  const len = Math.hypot(dx, dy) || 1
  const arc = Math.min(70, len * 0.2)
  const cx = (from.x + to.x) / 2 - (dy / len) * arc
  const cy = (from.y + to.y) / 2 + (dx / len) * arc
  return `M ${from.x} ${from.y} Q ${cx} ${cy} ${to.x} ${to.y}`
}

async function handleGenerateMap() {
  await mapStore.generateMap()
  fitToJourney()
}

async function loadMap() {
  // Reload the timeline when it is empty or still holds another session's events.
  const timelineReady =
    timelineStore.sessionId !== sessionStore.sessionId ||
    (timelineStore.events.length === 0 && !timelineStore.loading)
      ? timelineStore.fetchEvents()
      : Promise.resolve()

  await Promise.all([mapStore.fetchMap(), timelineReady])
  fitToJourney()
  const placeId = mapStore.resolvePlaceQuery(
    typeof route.query.place === 'string' ? route.query.place : null,
  )
  if (placeId && mapStore.nodes.some((node) => node.id === placeId)) {
    await mapStore.selectPlace(placeId)
  }
}

onMounted(() => {
  void loadMap()
  window.addEventListener('keydown', onKeydown)
})

onUnmounted(() => {
  window.removeEventListener('keydown', onKeydown)
})

// The active session changed (new game, saved, loaded): show that session only.
watch(
  () => sessionStore.sessionId,
  () => {
    selectedEdgeKey.value = null
    void loadMap()
  },
)

watch(
  () => route.query.place,
  async (place) => {
    if (typeof place !== 'string' || !place.trim()) {
      mapStore.clearSelection()
      selectedEdgeKey.value = null
      return
    }
    const placeId = mapStore.resolvePlaceQuery(place)
    if (placeId && mapStore.nodes.some((node) => node.id === placeId)) {
      await mapStore.selectPlace(placeId)
    }
  },
)
</script>

<template>
  <div class="map-page">
    <div class="map-shell">
      <header class="map-header">
        <div class="title-group">
          <button class="back-btn" @click="goBack">← Back to Dashboard</button>
          <div>
            <p class="eyebrow">Campaign Journey</p>
            <h1>Geographic Map</h1>
          </div>
        </div>
        <div class="header-actions">
          <button class="btn btn-secondary" @click="goToTimeline">Open Timeline</button>
          <button class="btn btn-secondary" type="button" @click="fitToJourney">Fit journey</button>
          <button
            v-if="mapStore.selectedNode || selectedEdge"
            class="btn btn-secondary"
            type="button"
            @click="clearSelection"
          >
            Clear selection
          </button>
          <button
            class="btn btn-primary"
            :disabled="mapStore.loading || mapStore.generating"
            @click="handleGenerateMap"
          >
            {{ mapStore.generating ? 'Generating...' : 'Generate map' }}
          </button>
          <button class="btn btn-secondary" :disabled="mapStore.loading" @click="loadMap">
            {{ mapStore.loading ? 'Loading...' : 'Refresh Map' }}
          </button>
        </div>
      </header>

      <p v-if="mapStore.dataSource === 'timeline'" class="info-banner">
        Map API unavailable. Showing places inferred from timeline events.
      </p>

      <div v-if="mapStore.error" class="error-banner">
        {{ mapStore.error }}
      </div>

      <div v-if="mapStore.loading" class="loading">Loading map...</div>

      <div v-else-if="mapStore.nodeCount === 0" class="empty-state">
        <p>No places on the map yet.</p>
        <p>Record and transcribe a session, generate timeline events, then generate this map.</p>
        <button class="btn btn-primary" @click="goToTimeline">Go to Timeline</button>
      </div>

      <div v-else class="map-layout">
        <section class="map-canvas-panel">
          <div class="map-meta">
            <span>{{ mapStore.nodeCount }} places</span>
            <span>{{ mapStore.edgeCount }} links</span>
            <span class="hint">Scroll to zoom · drag empty space to pan · ← → to step</span>
          </div>
          <p v-if="journeyOrderLine" class="journey-line">{{ journeyOrderLine }}</p>

          <svg
            ref="svgRef"
            class="map-canvas"
            :viewBox="`0 0 ${layout.width} ${layout.height}`"
            preserveAspectRatio="xMidYMid meet"
            role="img"
            aria-label="Campaign place map showing the party's journey"
            :style="{ aspectRatio: canvasAspect, cursor: isPanning ? 'grabbing' : 'grab' }"
            @wheel.prevent="onWheel"
            @pointerdown="onPointerDown"
            @pointermove="onPointerMove"
            @pointerup="onPointerUp"
            @pointerleave="onPointerUp"
          >
            <defs>
              <marker
                id="arrow-traveled"
                markerWidth="10"
                markerHeight="10"
                refX="9"
                refY="5"
                orient="auto"
                markerUnits="userSpaceOnUse"
              >
                <path d="M0,0 L10,5 L0,10 Z" fill="#b45309" />
              </marker>
              <filter id="node-shadow" x="-50%" y="-50%" width="200%" height="200%">
                <feDropShadow
                  dx="0"
                  dy="3"
                  stdDeviation="4"
                  flood-color="#2b1c04"
                  flood-opacity="0.35"
                />
              </filter>
              <pattern id="parchment-grain" width="48" height="48" patternUnits="userSpaceOnUse">
                <rect width="48" height="48" fill="rgba(226, 208, 160, 0.35)" />
                <circle cx="8" cy="12" r="1.2" fill="rgba(120, 92, 30, 0.12)" />
                <circle cx="28" cy="30" r="1" fill="rgba(120, 92, 30, 0.1)" />
                <circle cx="40" cy="8" r="0.8" fill="rgba(120, 92, 30, 0.08)" />
              </pattern>
            </defs>

            <rect
              class="canvas-backdrop"
              x="0"
              y="0"
              :width="layout.width"
              :height="layout.height"
              fill="url(#parchment-grain)"
            />

            <g :transform="viewportTransform">
              <g class="edges">
                <g
                  v-for="(edge, index) in mapStore.edges"
                  :key="edgeKey(edge, index)"
                  class="edge-group"
                  :class="{
                    dimmed: highlightedPlaceId && !edgeTouchesSelection(edge.from, edge.to),
                    active:
                      edgeTouchesSelection(edge.from, edge.to) ||
                      selectedEdgeKey === edgeKey(edge, index),
                  }"
                  @click.stop="handleSelectEdge(edge, index)"
                >
                  <title>
                    {{ edgeLabels[edge.type] || 'Linked' }}: {{ nodeLabel(edge.from) }} →
                    {{ nodeLabel(edge.to) }}
                  </title>
                  <path :d="edgePath(edge.from, edge.to)" class="edge-hit" />
                  <path
                    :d="edgePath(edge.from, edge.to)"
                    class="edge-line"
                    :class="{ proximity: edge.type !== 'traveled' }"
                    :stroke="edgeColors[edge.type] || edgeColors.other"
                    :marker-end="edge.type === 'traveled' ? 'url(#arrow-traveled)' : undefined"
                  />
                  <g v-if="edge.type === 'traveled' && edgeMidpoint(edge.from, edge.to)">
                    <circle
                      :cx="edgeMidpoint(edge.from, edge.to)!.x"
                      :cy="edgeMidpoint(edge.from, edge.to)!.y"
                      r="11"
                      class="path-marker"
                    />
                    <text
                      :x="edgeMidpoint(edge.from, edge.to)!.x"
                      :y="edgeMidpoint(edge.from, edge.to)!.y + 4"
                      class="path-marker-text"
                    >
                      {{ index + 1 }}
                    </text>
                  </g>
                </g>
              </g>

              <g class="nodes">
                <g
                  v-for="(node, index) in mapStore.nodes"
                  :key="node.id"
                  class="node-group"
                  :class="{
                    highlighted: highlightedPlaceId === node.id,
                    dimmed: nodeDimmed(node.id),
                  }"
                  role="button"
                  tabindex="0"
                  :aria-label="`Place ${index + 1}: ${node.label}`"
                  @click.stop="handleSelectPlace(node.id)"
                  @keyup.enter="handleSelectPlace(node.id)"
                >
                  <title>
                    {{ node.label }}<template v-if="node.aliases?.length"> (also:
                    {{ node.aliases.join(', ') }})</template >
                  </title>

                  <text
                    v-if="isStart(index) || isEnd(index)"
                    :x="nodePositions.get(node.id)?.x"
                    :y="(nodePositions.get(node.id)?.y ?? 0) - 52"
                    class="node-flag"
                  >
                    {{ isStart(index) ? 'START' : 'END' }}
                  </text>

                  <circle
                    :cx="nodePositions.get(node.id)?.x"
                    :cy="nodePositions.get(node.id)?.y"
                    r="34"
                    class="node-circle"
                    filter="url(#node-shadow)"
                  />
                  <text
                    :x="nodePositions.get(node.id)?.x"
                    :y="(nodePositions.get(node.id)?.y ?? 0) - 2"
                    class="node-icon"
                  >
                    {{ placeIcon(node.label) }}
                  </text>
                  <text
                    :x="nodePositions.get(node.id)?.x"
                    :y="(nodePositions.get(node.id)?.y ?? 0) + 18"
                    class="node-index"
                  >
                    {{ index + 1 }}
                  </text>
                  <text
                    :x="nodePositions.get(node.id)?.x"
                    :y="(nodePositions.get(node.id)?.y ?? 0) + 60"
                    class="node-label"
                  >
                    {{ truncateLabel(node.label) }}
                  </text>
                </g>
              </g>
            </g>
          </svg>

          <div class="legend">
            <span v-for="type in activeLegend" :key="type" class="legend-item">
              <i
                :class="{ dashed: type !== 'traveled' }"
                :style="{ background: edgeColors[type] }"
              ></i>
              {{ edgeLabels[type] }}
            </span>
          </div>
        </section>

        <aside class="map-sidebar">
          <h2>Place details</h2>

          <div v-if="!mapStore.selectedNode" class="sidebar-empty">
            Click a place on the map to see related timeline events.
          </div>

          <template v-else>
            <div class="selected-place-card">
              <p class="sidebar-eyebrow">Selected place</p>
              <h3>
                <span class="sidebar-icon">{{ placeIcon(mapStore.selectedNode.label) }}</span>
                {{ mapStore.selectedNode.label }}
              </h3>
              <p v-if="mapStore.selectedNode.aliases?.length" class="sidebar-aliases">
                Also known as: {{ mapStore.selectedNode.aliases.join(', ') }}
              </p>
            </div>

            <div v-if="selectedEdge" class="link-card">
              <p class="sidebar-eyebrow">Selected path</p>
              <p>
                {{ edgeLabels[selectedEdge.type] }}: {{ nodeLabel(selectedEdge.from) }} →
                {{ nodeLabel(selectedEdge.to) }}
              </p>
            </div>

            <div v-if="selectedLinks.length" class="links-block">
              <p class="sidebar-eyebrow">Connected paths</p>
              <ul class="link-list">
                <li v-for="link in selectedLinks" :key="link.key">
                  <button type="button" class="link-chip" @click="handleSelectPlace(link.otherId)">
                    {{ link.label }} {{ link.direction }} {{ truncateLabel(link.otherLabel, 20) }}
                  </button>
                </li>
              </ul>
            </div>

            <div v-if="selectedEvents.length === 0" class="sidebar-empty">
              No timeline events linked to this place yet.
            </div>

            <ul v-else class="event-list">
              <li v-for="event in selectedEvents" :key="event.id">
                <button class="event-link" @click="openTimelineEvent(event.id)">
                  <span class="event-type">{{ event.event_type }}</span>
                  <strong>{{ event.title }}</strong>
                  <span class="event-time">{{ event.display_time || '—' }}</span>
                </button>
              </li>
            </ul>
          </template>
        </aside>
      </div>
    </div>
  </div>
</template>

<style scoped>
.map-page {
  position: fixed;
  inset: 0;
  z-index: 500;
  width: 100vw;
  min-height: 100vh;
  padding: 60px 1.25rem 1.25rem;
  background-image: url('/bg-texture.jpg');
  background-size: cover;
  background-position: center;
  background-attachment: fixed;
  background-color: rgba(36, 25, 7, 0.95);
  color: #392401;
  box-sizing: border-box;
  overflow-x: hidden;
  overflow-y: auto;
}

.map-shell {
  max-width: 1280px;
  width: 100%;
  height: auto;
  margin: 0 auto;
  padding: 1.4rem;
  border-radius: 14px;
  background-color: rgba(163, 148, 95, 0.85);
  border: 1px solid rgba(105, 87, 16, 0.5);
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
  display: flex;
  flex-direction: column;
  overflow: visible;
}

.map-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
  margin-bottom: 1rem;
  flex-wrap: wrap;
  flex-shrink: 0;
}

.title-group {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}

.eyebrow,
.sidebar-eyebrow {
  margin: 0;
  color: #695710;
  font-size: 0.78rem;
  font-weight: 700;
  letter-spacing: 0.14em;
  text-transform: uppercase;
}

.sidebar-aliases {
  margin: 0.4rem 0 0;
  color: #5c4a24;
  font-size: 0.9rem;
}

.sidebar-icon {
  margin-right: 0.25rem;
}

.map-header h1,
.map-sidebar h2,
.selected-place-card h3 {
  margin: 0;
  font-family: 'MedievalSharp', cursive;
  color: #392401;
}

.map-header h1 {
  font-size: 1.6rem;
}

.header-actions {
  display: flex;
  gap: 0.6rem;
  flex-wrap: wrap;
}

.back-btn,
.btn {
  padding: 0.5rem 0.85rem;
  border: 1px solid #8e7513;
  border-radius: 10px;
  cursor: pointer;
  font-size: 0.9rem;
  font-weight: 700;
  font-family: 'MedievalSharp', cursive;
  transition: all 0.2s ease;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.15);
}

.back-btn {
  align-self: flex-start;
  background-color: #b74d30;
  color: white;
}

.back-btn:hover {
  background-color: #7e6f34;
}

.btn-primary {
  background-color: #695710;
  color: #fff;
}

.btn-secondary {
  background-color: rgba(57, 36, 1, 0.14);
  border-color: rgba(57, 36, 1, 0.3);
  color: #392401;
}

.btn-secondary:hover:not(:disabled) {
  background-color: rgba(57, 36, 1, 0.24);
}

.btn:disabled {
  opacity: 0.65;
  cursor: not-allowed;
}

.info-banner,
.error-banner {
  margin-bottom: 0.75rem;
  padding: 0.65rem 0.85rem;
  border-radius: 10px;
  font-size: 0.9rem;
}

.info-banner {
  background: rgba(52, 152, 219, 0.15);
  border: 1px solid rgba(52, 152, 219, 0.35);
}

.error-banner {
  background: rgba(231, 76, 60, 0.15);
  border: 1px solid rgba(231, 76, 60, 0.35);
}

.loading,
.empty-state,
.sidebar-empty {
  color: #4c3e06;
}

.empty-state {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0.75rem;
  text-align: center;
}

.map-layout {
  flex: 0 0 auto;
  display: grid;
  grid-template-columns: minmax(0, 1.4fr) minmax(260px, 0.8fr);
  gap: 1rem;
  align-items: start;
}

.map-canvas-panel,
.map-sidebar {
  border-radius: 12px;
  background: rgba(255, 248, 220, 0.55);
  border: 1px solid rgba(105, 87, 16, 0.25);
}

.map-canvas-panel {
  display: flex;
  flex-direction: column;
  padding: 0.85rem;
  height: auto;
}

.map-meta {
  display: flex;
  gap: 1rem;
  margin-bottom: 0.35rem;
  font-size: 0.85rem;
  font-weight: 700;
  color: #695710;
  flex-wrap: wrap;
  align-items: center;
}

.map-meta .hint {
  font-weight: 500;
  opacity: 0.85;
}

.journey-line {
  margin: 0 0 0.55rem;
  font-size: 0.82rem;
  color: #4c3e06;
  line-height: 1.35;
}

.map-canvas {
  width: 100%;
  flex: 0 0 auto;
  height: auto;
  max-height: min(62vh, 560px);
  min-height: 0;
  display: block;
  background: radial-gradient(
    circle at 30% 20%,
    rgba(255, 251, 235, 0.95),
    rgba(244, 232, 200, 0.88) 55%,
    rgba(226, 208, 160, 0.9) 100%
  );
  border: 1px solid rgba(105, 87, 16, 0.3);
  border-radius: 12px;
  box-shadow: inset 0 0 40px rgba(120, 92, 30, 0.25);
  touch-action: none;
}

.edge-group {
  transition: opacity 0.2s ease;
  cursor: pointer;
}

.edge-group.dimmed {
  opacity: 0.2;
}

.edge-hit {
  fill: none;
  stroke: transparent;
  stroke-width: 14;
}

.edge-line {
  fill: none;
  stroke-width: 3.5;
  opacity: 0.9;
  stroke-linecap: round;
  pointer-events: none;
}

.edge-line.proximity {
  stroke-dasharray: 6 7;
  opacity: 0.75;
}

.edge-group.active .edge-line {
  stroke-width: 5;
  opacity: 1;
}

.path-marker {
  fill: #f1e6b4;
  stroke: #b45309;
  stroke-width: 2;
}

.path-marker-text {
  text-anchor: middle;
  font-size: 10px;
  font-weight: 700;
  fill: #4a3403;
  pointer-events: none;
}

.node-group {
  cursor: pointer;
  transition: opacity 0.2s ease;
}

.node-group:focus {
  outline: none;
}

.node-group.dimmed {
  opacity: 0.32;
}

.node-circle {
  fill: #e2c583;
  stroke: #8e7513;
  stroke-width: 3;
  transition: all 0.2s ease;
}

.node-group:hover .node-circle,
.node-group:focus .node-circle,
.node-group.highlighted .node-circle {
  fill: #f4b95a;
  stroke: #b45309;
  stroke-width: 4.5;
}

.node-icon {
  text-anchor: middle;
  font-size: 16px;
  pointer-events: none;
}

.node-index {
  text-anchor: middle;
  font-size: 12px;
  font-weight: 700;
  fill: #4a3403;
  font-family: 'MedievalSharp', cursive;
  pointer-events: none;
}

.node-flag {
  text-anchor: middle;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.14em;
  fill: #b45309;
  pointer-events: none;
}

.node-label {
  text-anchor: middle;
  font-size: 15px;
  font-weight: 700;
  fill: #2f1e02;
  font-family: 'MedievalSharp', cursive;
  pointer-events: none;
  paint-order: stroke;
  stroke: rgba(255, 250, 235, 0.9);
  stroke-width: 3px;
}

.legend {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
  margin-top: 0.75rem;
  font-size: 0.8rem;
}

.legend-item {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
}

.legend-item i {
  width: 14px;
  height: 3px;
  border-radius: 999px;
  display: inline-block;
}

.legend-item i.dashed {
  background-image: repeating-linear-gradient(90deg, currentColor 0 4px, transparent 4px 8px);
}

.map-sidebar {
  padding: 1rem;
  overflow: auto;
  min-height: 0;
  max-height: min(62vh, 560px);
  align-self: stretch;
}

.map-sidebar h2 {
  font-size: 1.15rem;
  margin-bottom: 0.75rem;
}

.selected-place-card,
.link-card {
  padding: 0.75rem;
  margin-bottom: 0.85rem;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.45);
  border: 1px solid rgba(142, 117, 19, 0.25);
}

.links-block {
  margin-bottom: 0.85rem;
}

.link-list {
  list-style: none;
  margin: 0.4rem 0 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.link-chip {
  width: 100%;
  text-align: left;
  padding: 0.4rem 0.55rem;
  border-radius: 8px;
  border: 1px solid rgba(142, 117, 19, 0.3);
  background: rgba(255, 255, 255, 0.5);
  cursor: pointer;
  font-size: 0.82rem;
  color: #392401;
  font-family: 'MedievalSharp', cursive;
}

.link-chip:hover {
  background: rgba(243, 156, 18, 0.18);
}

.event-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.55rem;
}

.event-link {
  width: 100%;
  text-align: left;
  padding: 0.75rem;
  border: 1px solid rgba(142, 117, 19, 0.25);
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.55);
  cursor: pointer;
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  color: #392401;
  font-family: inherit;
}

.event-link:hover {
  background: rgba(243, 156, 18, 0.18);
}

.event-type {
  font-size: 0.72rem;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: #695710;
  font-weight: 700;
}

.event-time {
  font-size: 0.8rem;
  color: #b45309;
}

@media (max-width: 900px) {
  .map-layout {
    grid-template-columns: 1fr;
  }

  .map-sidebar {
    max-height: none;
  }
}
</style>
