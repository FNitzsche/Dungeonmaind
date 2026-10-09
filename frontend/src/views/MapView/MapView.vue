<script setup lang="ts">
import { computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { mapSample } from '@/fixtures/mapSample'
import { useMapStore } from '@/stores/map'
import MapGraph from './components/MapGraph.vue'

const router = useRouter()
const route = useRoute()
const mapStore = useMapStore()
const sampleMode = computed(() => route.query.demo === 'sample')
const busy = computed(() => mapStore.loading || mapStore.generating)
const displayedMap = computed(() => (sampleMode.value ? mapSample : mapStore.mapData))

// Explicit URL opt-in permits opening the demo without requesting /map.
// Sample data never enters the Pinia store or the API client.
watch(
  sampleMode,
  (sample) => {
    if (!sample) void mapStore.loadMap()
  },
  { immediate: true },
)

function setSampleMode(sample: boolean): void {
  if (busy.value) return
  const query = { ...route.query }
  if (sample) query.demo = 'sample'
  else delete query.demo
  void router.replace({ name: 'map', query })
}
</script>

<template>
  <main class="map-page">
    <header class="map-header">
      <button type="button" class="back-button" @click="router.push({ name: 'home' })">
        ← Back to session
      </button>
      <div>
        <h1>Geographic Map</h1>
        <p>Review locations and geographic relationships from the current session.</p>
      </div>
      <button
        type="button"
        class="generate-button"
        :disabled="busy || sampleMode"
        @click="mapStore.generateMap"
      >
        {{ mapStore.generating ? 'Generating…' : 'Generate Map' }}
      </button>
    </header>

    <section class="mode-panel" aria-label="Map data mode">
      <template v-if="sampleMode">
        <p><strong>Sample demo — invented data, not extracted session results.</strong></p>
        <p>Generation is disabled in demo mode. No map API requests are made.</p>
        <button type="button" :disabled="busy" @click="setSampleMode(false)">
          Use session data
        </button>
      </template>
      <template v-else>
        <p>Session data mode. Map generation runs only when you click Generate Map.</p>
        <button type="button" :disabled="busy" @click="setSampleMode(true)">
          Show sample demo
        </button>
      </template>
    </section>

    <section v-if="!sampleMode && busy" class="status-panel" role="status" aria-live="polite">
      {{ mapStore.generating ? 'Generating the geographic map…' : 'Loading the geographic map…' }}
    </section>

    <section
      v-else-if="!sampleMode && mapStore.error"
      class="status-panel error-panel"
      role="alert"
    >
      <h2>Could not retrieve the geographic map</h2>
      <p>{{ mapStore.error }}</p>
      <button type="button" @click="mapStore.loadMap">Retry loading</button>
      <p>You can also choose Show sample demo to preview invented data.</p>
    </section>

    <section
      v-else-if="!displayedMap || (!displayedMap.nodes.length && !displayedMap.edges.length)"
      class="status-panel"
    >
      <h2>No geographic map yet</h2>
      <p>
        Record or upload a session, then click Generate Map to extract its locations and
        relationships.
      </p>
    </section>

    <section
      v-else
      class="data-panel"
      :aria-label="sampleMode ? 'Sample map data' : 'Session map data'"
    >
      <h2>{{ sampleMode ? 'Sample map data' : 'Session map data' }}</h2>
      <p>
        {{ displayedMap.nodes.length }} locations · {{ displayedMap.edges.length }} relationships ·
        {{ displayedMap.source_segment_count }} source segments
      </p>
      <MapGraph :key="sampleMode ? 'sample' : 'session'" :data="displayedMap" />
    </section>
  </main>
</template>

<style src="@/assets/styles.css"></style>

<style scoped>
.map-page {
  width: min(1050px, calc(100% - 2rem));
  margin: 2rem auto;
  padding: 1.5rem;
  box-sizing: border-box;
}

.map-header {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: center;
  gap: 1.5rem;
  padding: 1.5rem;
  border: 1px solid rgba(255, 239, 190, 0.25);
  border-radius: 18px;
  background: rgba(154, 124, 64, 0.94);
  color: #fff5d4;
  box-shadow: 0 8px 30px rgba(26, 14, 2, 0.38);
}

.map-header h1 {
  padding: 0;
  margin: 0;
  text-align: left;
}

.map-page p {
  line-height: 1.5;
  overflow-wrap: anywhere;
}

button {
  padding: 0.7rem 1rem;
  border: 1px solid #4a575e;
  border-radius: 10px;
  color: white;
  background: rgba(53, 73, 94, 0.95);
  cursor: pointer;
  font-family: 'MedievalSharp', cursive;
}

.generate-button {
  background: #8f3f28;
  border-color: #6a3b1d;
}

button:disabled {
  opacity: 0.65;
  cursor: not-allowed;
}

button:enabled:hover {
  filter: brightness(1.08);
}

button:focus-visible {
  outline: 3px solid #f2df9e;
  outline-offset: 2px;
}

.mode-panel,
.status-panel,
.data-panel {
  margin-top: 1.25rem;
  padding: 1.5rem;
  border-radius: 14px;
  color: #392401;
  background: rgba(224, 202, 139, 0.95);
}

.mode-panel {
  border: 2px solid #705820;
}

.status-panel {
  text-align: center;
}

.error-panel {
  color: #7d1d18;
}

@media (max-width: 760px) {
  .map-page {
    padding: 0;
  }

  .map-header {
    grid-template-columns: 1fr;
  }

  button {
    width: 100%;
  }
}
</style>
