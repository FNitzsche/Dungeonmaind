<script setup lang="ts">
/**
 * MapEditPanel – leader-only DM corrections for the selected place:
 * rename, merge, split, connect, and disconnect.
 */
import { computed, ref, watch } from 'vue'
import type { MapEdgeType } from '@/api/mapAPI'
import { useMapStore } from '@/stores/map'
import { useSessionStore } from '@/stores/session'
import { useTimelineStore } from '@/stores/timeline'

const mapStore = useMapStore()
const sessionStore = useSessionStore()
const timelineStore = useTimelineStore()

const renameTo = ref('')
const mergeTargetId = ref('')
const splitName = ref('')
const splitEventIds = ref<string[]>([])
const connectToId = ref('')
const connectType = ref<MapEdgeType>('traveled')

const canEdit = computed(
  () => sessionStore.isLeader && mapStore.apiStatus !== 'down' && Boolean(mapStore.selectedNode),
)

const otherPlaces = computed(() =>
  mapStore.nodes.filter((node) => node.id !== mapStore.selectedPlaceId),
)

const linkedEdges = computed(() => {
  const selected = mapStore.selectedPlaceId
  if (!selected) return []
  return mapStore.edges.filter((edge) => edge.from === selected || edge.to === selected)
})

const placeEvents = computed(() => {
  const ids = new Set(
    mapStore.selectedEventIds.length
      ? mapStore.selectedEventIds
      : (mapStore.selectedNode?.event_ids ?? []),
  )
  const fromTimeline = timelineStore.events.filter((event) => ids.has(event.id))
  if (fromTimeline.length) return fromTimeline
  return [...ids].map((id) => ({ id, title: id, event_type: '', display_time: '' }))
})

watch(
  () => mapStore.selectedPlaceId,
  () => {
    renameTo.value = mapStore.selectedNode?.label ?? ''
    mergeTargetId.value = otherPlaces.value[0]?.id ?? ''
    splitName.value = ''
    splitEventIds.value = []
    connectToId.value = otherPlaces.value[0]?.id ?? ''
    connectType.value = 'traveled'
  },
  { immediate: true },
)

function toggleSplitEvent(eventId: string) {
  if (splitEventIds.value.includes(eventId)) {
    splitEventIds.value = splitEventIds.value.filter((id) => id !== eventId)
  } else {
    splitEventIds.value = [...splitEventIds.value, eventId]
  }
}

async function onRename() {
  const node = mapStore.selectedNode
  const name = renameTo.value.trim()
  if (!node || !name || name === node.label) return
  await mapStore.renamePlace(node.id, name)
}

async function onMerge() {
  const node = mapStore.selectedNode
  if (!node || !mergeTargetId.value) return
  await mapStore.mergePlaces([node.id], mergeTargetId.value)
}

async function onSplit() {
  const node = mapStore.selectedNode
  const name = splitName.value.trim()
  if (!node || !name || splitEventIds.value.length === 0) return
  await mapStore.splitPlace(node.id, name, splitEventIds.value)
}

async function onConnect() {
  const node = mapStore.selectedNode
  if (!node || !connectToId.value) return
  await mapStore.connectPlaces(node.id, connectToId.value, connectType.value)
}

async function onDisconnect(fromId: string, toId: string, type: MapEdgeType) {
  await mapStore.disconnectPlaces(fromId, toId, type)
}

function otherLabel(edgeFrom: string, edgeTo: string): string {
  const selected = mapStore.selectedPlaceId
  const otherId = edgeFrom === selected ? edgeTo : edgeFrom
  return mapStore.nodes.find((node) => node.id === otherId)?.label ?? otherId
}
</script>

<template>
  <section v-if="sessionStore.isLeader" class="edit-panel">
    <p class="sidebar-eyebrow">Edit place</p>
    <p v-if="mapStore.apiStatus === 'down'" class="edit-hint">
      Map API is unreachable, so edits cannot be saved.
    </p>
    <template v-else-if="canEdit">
      <form class="edit-block" @submit.prevent="onRename">
        <label for="map-rename">Rename</label>
        <div class="edit-row">
          <input
            id="map-rename"
            v-model.trim="renameTo"
            class="edit-input"
            maxlength="80"
            :disabled="mapStore.saving"
          />
          <button
            class="btn btn-secondary"
            type="submit"
            :disabled="mapStore.saving || !renameTo || renameTo === mapStore.selectedNode?.label"
          >
            Save
          </button>
        </div>
      </form>

      <form class="edit-block" @submit.prevent="onMerge">
        <label for="map-merge">Merge into</label>
        <div class="edit-row">
          <select
            id="map-merge"
            v-model="mergeTargetId"
            class="edit-input"
            :disabled="mapStore.saving || otherPlaces.length === 0"
          >
            <option v-for="place in otherPlaces" :key="place.id" :value="place.id">
              {{ place.label }}
            </option>
          </select>
          <button
            class="btn btn-secondary"
            type="submit"
            :disabled="mapStore.saving || !mergeTargetId"
          >
            Merge
          </button>
        </div>
        <p class="edit-hint">This place is absorbed; the chosen place keeps the pin.</p>
      </form>

      <form class="edit-block" @submit.prevent="onSplit">
        <label for="map-split-name">Split off as</label>
        <input
          id="map-split-name"
          v-model.trim="splitName"
          class="edit-input"
          maxlength="80"
          placeholder="New place name"
          :disabled="mapStore.saving"
        />
        <p v-if="placeEvents.length === 0" class="edit-hint">No events to move onto a new place.</p>
        <ul v-else class="split-events">
          <li v-for="event in placeEvents" :key="event.id">
            <label>
              <input
                type="checkbox"
                :checked="splitEventIds.includes(event.id)"
                :disabled="mapStore.saving"
                @change="toggleSplitEvent(event.id)"
              />
              {{ event.title || event.id }}
            </label>
          </li>
        </ul>
        <button
          class="btn btn-secondary"
          type="submit"
          :disabled="mapStore.saving || !splitName || splitEventIds.length === 0"
        >
          Split
        </button>
      </form>

      <form class="edit-block" @submit.prevent="onConnect">
        <label for="map-connect">Connect to</label>
        <div class="edit-row">
          <select
            id="map-connect"
            v-model="connectToId"
            class="edit-input"
            :disabled="mapStore.saving || otherPlaces.length === 0"
          >
            <option v-for="place in otherPlaces" :key="place.id" :value="place.id">
              {{ place.label }}
            </option>
          </select>
          <select
            v-model="connectType"
            class="edit-input edit-input--narrow"
            :disabled="mapStore.saving"
            aria-label="Link type"
          >
            <option value="traveled">Travel</option>
            <option value="near">Near</option>
          </select>
          <button
            class="btn btn-secondary"
            type="submit"
            :disabled="mapStore.saving || !connectToId"
          >
            Connect
          </button>
        </div>
      </form>

      <div v-if="linkedEdges.length" class="edit-block">
        <p class="edit-label">Disconnect</p>
        <ul class="split-events">
          <li v-for="edge in linkedEdges" :key="`${edge.from}->${edge.to}:${edge.type}`">
            <span>{{ otherLabel(edge.from, edge.to) }}</span>
            <button
              class="btn btn-secondary"
              type="button"
              :disabled="mapStore.saving"
              @click="onDisconnect(edge.from, edge.to, edge.type)"
            >
              Remove
            </button>
          </li>
        </ul>
      </div>
    </template>
  </section>
</template>

<style scoped>
.edit-panel {
  margin: 0 0 0.85rem;
  padding: 0.75rem;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.45);
  border: 1px solid rgba(142, 117, 19, 0.25);
}

.sidebar-eyebrow {
  margin: 0 0 0.55rem;
  color: #695710;
  font-size: 0.78rem;
  font-weight: 700;
  letter-spacing: 0.14em;
  text-transform: uppercase;
}

.edit-block {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  margin-bottom: 0.75rem;
}

.edit-block:last-child {
  margin-bottom: 0;
}

.edit-block label,
.edit-label {
  font-size: 0.78rem;
  font-weight: 700;
  color: #695710;
}

.edit-row {
  display: flex;
  gap: 0.4rem;
  align-items: stretch;
}

.edit-input {
  flex: 1;
  min-width: 0;
  padding: 0.4rem 0.5rem;
  border-radius: 8px;
  border: 1px solid rgba(142, 117, 19, 0.35);
  background: rgba(255, 255, 255, 0.75);
  color: #392401;
  font-family: inherit;
}

.edit-input--narrow {
  flex: 0 0 5.5rem;
}

.edit-hint {
  margin: 0;
  font-size: 0.78rem;
  color: #5c4a24;
}

.split-events {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
}

.split-events li {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.4rem;
  font-size: 0.82rem;
}

.split-events label {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  font-weight: 500;
  color: #392401;
}

.btn {
  padding: 0.4rem 0.7rem;
  border: 1px solid #8e7513;
  border-radius: 10px;
  cursor: pointer;
  font-size: 0.82rem;
  font-weight: 700;
  font-family: 'MedievalSharp', cursive;
}

.btn-secondary {
  background-color: rgba(57, 36, 1, 0.14);
  border-color: rgba(57, 36, 1, 0.3);
  color: #392401;
  white-space: nowrap;
}

.btn:disabled {
  opacity: 0.65;
  cursor: not-allowed;
}
</style>
