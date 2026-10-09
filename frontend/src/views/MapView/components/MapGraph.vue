<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import cytoscape, { type Core } from 'cytoscape'
import type { MapData } from '@/api/mapAPI'
import { formatSessionTime, toGraphElements } from './mapGraph'

const props = defineProps<{ data: MapData }>()
const container = ref<HTMLDivElement | null>(null)
const selection = ref<{ kind: 'node' | 'edge'; id: string } | null>(null)
const renderError = ref(false)
let graph: Core | undefined
let observer: ResizeObserver | undefined

const selectedNode = computed(() =>
  selection.value?.kind === 'node'
    ? props.data.nodes.find((node) => node.id === selection.value?.id)
    : undefined,
)
const selectedEdge = computed(() =>
  selection.value?.kind === 'edge'
    ? props.data.edges.find((edge) => edge.id === selection.value?.id)
    : undefined,
)
const hasDanglingEdges = computed(() => {
  const ids = new Set(props.data.nodes.map((node) => node.id))
  return props.data.edges.some((edge) => !ids.has(edge.source) || !ids.has(edge.target))
})

function locationName(id: string): string {
  return props.data.nodes.find((node) => node.id === id)?.name ?? id
}

function clearSelection(): void {
  graph?.elements().unselect()
  selection.value = null
}

function select(kind: 'node' | 'edge', id: string): void {
  clearSelection()
  // getElementById accepts IDs literally, including punctuation used in API IDs.
  const element = graph?.getElementById(id)
  if (element && (kind === 'node' ? element.isNode() : element.isEdge())) element.select()
  selection.value = { kind, id }
}

function fit(): void {
  graph?.resize()
  graph?.fit(undefined, 40)
}

function destroyGraph(): void {
  observer?.disconnect()
  observer = undefined
  graph?.destroy()
  graph = undefined
}

function smallNetworkLayout() {
  return {
    name: (container.value?.clientWidth ?? 0) < 480 ? 'grid' : 'circle',
    cols: 1,
    padding: 40,
    nodeDimensionsIncludeLabels: true,
    avoidOverlap: true,
  }
}

function renderGraph(): void {
  destroyGraph()
  selection.value = null
  renderError.value = false
  if (!container.value || !props.data.nodes.length) return

  try {
    graph = cytoscape({
      container: container.value,
      elements: toGraphElements(props.data),
      selectionType: 'single',
      boxSelectionEnabled: false,
      minZoom: 0.1,
      maxZoom: 3,
      // Small networks use a circle, or a single column on narrow screens; larger ones use CoSE.
      layout:
        props.data.nodes.length <= 12
          ? smallNetworkLayout()
          : {
              name: 'cose',
              animate: false,
              randomize: true,
              padding: 40,
              nodeDimensionsIncludeLabels: true,
              nodeRepulsion: () => 2048,
              idealEdgeLength: () => 60,
            },
      style: [
        {
          selector: 'node',
          style: {
            label: 'data(label)',
            'background-color': '#35495e',
            'border-width': 2,
            'border-color': '#f1e6b4',
            shape: 'round-rectangle',
            width: 160,
            height: 60,
            padding: '12px',
            color: '#fff5d4',
            'font-size': 16,
            'text-valign': 'center',
            'text-halign': 'center',
            'text-wrap': 'wrap',
            'text-max-width': '150px',
            'text-background-color': '#f1e6b4',
            'text-background-opacity': 0,
            'text-background-padding': '3px',
          },
        },
        {
          selector: 'edge',
          style: {
            label: 'data(label)',
            width: 2,
            'curve-style': 'bezier',
            'control-point-step-size': 70,
            'text-rotation': 'autorotate',
            'text-margin-y': -10,
            'target-arrow-shape': 'triangle',
            'line-color': '#705820',
            'target-arrow-color': '#705820',
            color: '#392401',
            'font-size': 14,
            'text-wrap': 'wrap',
            'text-max-width': '120px',
            'text-background-color': '#f1e6b4',
            'text-background-opacity': 1,
            'text-background-padding': '3px',
          },
        },
        {
          selector: 'node:selected',
          style: { 'background-color': '#b74d30', 'border-color': '#392401', 'border-width': 5 },
        },
        {
          selector: 'edge:selected',
          style: { 'line-color': '#b74d30', 'target-arrow-color': '#b74d30', width: 5 },
        },
      ],
    })
    graph.on('select', 'node, edge', (event) => {
      selection.value = { kind: event.target.isNode() ? 'node' : 'edge', id: event.target.id() }
    })
    graph.on('unselect', 'node, edge', (event) => {
      if (selection.value?.id === event.target.id()) selection.value = null
    })
    graph.on('tap', (event) => {
      if (event.target === graph) clearSelection()
    })
    if (typeof ResizeObserver !== 'undefined') {
      observer = new ResizeObserver(() => {
        graph?.resize()
        if (props.data.nodes.length <= 12) graph?.layout(smallNetworkLayout()).run()
        else graph?.fit(undefined, 40)
      })
      observer.observe(container.value)
    }
  } catch {
    destroyGraph()
    renderError.value = true
  }
}

onMounted(renderGraph)
watch(() => props.data, renderGraph, { deep: true, flush: 'post' })
onBeforeUnmount(destroyGraph)
</script>

<template>
  <div class="map-graph" @keydown.esc="clearSelection">
    <p>Locations form a schematic network. Placement does not represent direction or distance.</p>
    <div class="graph-toolbar">
      <button type="button" :disabled="!data.nodes.length || renderError" @click="fit">
        Fit to View
      </button>
      <button type="button" :disabled="!selection" @click="clearSelection">Clear selection</button>
      <span>Scroll or pinch to zoom; drag the background to pan. Select an item for details.</span>
    </div>
    <p v-if="!data.nodes.length" role="status">No locations to display.</p>
    <p v-if="renderError" role="alert">
      The graph could not be drawn. Use the accessible lists below to explore all map data.
    </p>
    <p v-if="hasDanglingEdges" role="status">
      Some relationships reference missing locations and are only shown in the relationship list.
    </p>
    <div class="graph-layout">
      <div
        v-show="data.nodes.length && !renderError"
        ref="container"
        class="graph-canvas"
        role="img"
        aria-label="Interactive location network. Keyboard users can select locations and relationships in the lists below."
      ></div>
      <section class="details-panel" aria-label="Selection details" aria-live="polite">
        <template v-if="selectedNode">
          <h3>{{ selectedNode.name }}</h3>
          <dl>
            <dt>Mentions</dt>
            <dd>{{ selectedNode.mentions }}</dd>
            <dt>First seen (session elapsed)</dt>
            <dd>{{ formatSessionTime(selectedNode.first_seen) }}</dd>
            <dt>Last seen (session elapsed)</dt>
            <dd>{{ formatSessionTime(selectedNode.last_seen) }}</dd>
          </dl>
        </template>
        <template v-else-if="selectedEdge">
          <h3>Relationship details</h3>
          <dl>
            <dt>Source</dt>
            <dd>{{ locationName(selectedEdge.source) }}</dd>
            <dt>Target</dt>
            <dd>{{ locationName(selectedEdge.target) }}</dd>
            <dt>Relation</dt>
            <dd>{{ selectedEdge.relation.replace(/_/g, ' ') }}</dd>
            <dt>Evidence</dt>
            <dd>{{ selectedEdge.evidence }}</dd>
            <dt>Timestamp (session elapsed)</dt>
            <dd>{{ formatSessionTime(selectedEdge.timestamp) }}</dd>
          </dl>
        </template>
        <template v-else>
          <h3>Selection details</h3>
          <p>
            Select a location or relationship in the graph or lists below. Clear selection or press
            Escape to deselect.
          </p>
        </template>
      </section>
    </div>
    <section aria-label="Accessible map data">
      <h3>Locations</h3>
      <ul v-if="data.nodes.length">
        <li v-for="node in data.nodes" :key="node.id">
          <button
            type="button"
            :aria-pressed="selection?.kind === 'node' && selection.id === node.id"
            @click="select('node', node.id)"
          >
            {{ node.name }} — {{ node.mentions }} mentions
          </button>
        </li>
      </ul>
      <p v-else>No locations found.</p>
      <h3>Relationships</h3>
      <ul v-if="data.edges.length">
        <li v-for="edge in data.edges" :key="edge.id">
          <button
            type="button"
            :aria-pressed="selection?.kind === 'edge' && selection.id === edge.id"
            @click="select('edge', edge.id)"
          >
            {{ locationName(edge.source) }} → {{ edge.relation.replace(/_/g, ' ') }} →
            {{ locationName(edge.target) }}
          </button>
          <p class="evidence">{{ edge.evidence }}</p>
        </li>
      </ul>
      <p v-else>No geographic relationships found.</p>
    </section>
  </div>
</template>

<style scoped>
.graph-toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.75rem;
  margin: 1rem 0;
}
.graph-toolbar span {
  flex: 1 1 16rem;
}
.graph-layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(210px, 0.4fr);
  gap: 1rem;
}
.graph-canvas {
  position: relative;
  overflow: hidden;
  height: clamp(320px, 55vh, 580px);
  min-width: 0;
  background: #f1e6b4;
  border: 1px solid #705820;
  border-radius: 10px;
}
.details-panel {
  min-width: 0;
  padding: 1rem;
  border: 1px solid #705820;
  border-radius: 10px;
  background: rgba(241, 230, 180, 0.6);
}
h3 {
  margin-top: 0;
}
dt {
  font-weight: 600;
  margin-top: 0.75rem;
}
dd {
  margin: 0.25rem 0 0;
  white-space: pre-wrap;
}
p,
dd,
button {
  overflow-wrap: anywhere;
}
li {
  margin: 0.75rem 0;
}
ul {
  padding-left: 1.25rem;
}
section[aria-label='Accessible map data'] {
  margin-top: 1.5rem;
}
.evidence {
  margin: 0.25rem 0;
  white-space: pre-wrap;
}
button {
  max-width: 100%;
  padding: 0.65rem 0.9rem;
  border: 1px solid #4a575e;
  border-radius: 8px;
  color: white;
  background: #35495e;
  cursor: pointer;
  font: inherit;
  text-align: left;
}
button[aria-pressed='true'] {
  background: #8f3f28;
  outline: 2px solid #392401;
  outline-offset: 2px;
}
button:focus-visible {
  outline: 3px solid #8f3f28;
  outline-offset: 3px;
}
button:disabled {
  opacity: 0.65;
  cursor: not-allowed;
}
@media (max-width: 760px) {
  .graph-layout {
    grid-template-columns: 1fr;
  }
}
</style>
