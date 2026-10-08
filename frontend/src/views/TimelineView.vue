<script setup lang="ts">
/**
 * TimelineView – displays session timeline events in a vertical timeline layout.
 * Supports filtering by event type, viewing details in a modal,
 * generating new events, and deleting individual or all events.
 */
import { onMounted, ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useTimelineStore } from '@/stores/timeline'
import { useSessionStore } from '@/stores/session'
import type { TimelineEventOut } from '@/api/timelineAPI'

const router = useRouter()
const timelineStore = useTimelineStore()
const sessionStore = useSessionStore()

const selectedEvent = ref<TimelineEventOut | null>(null)
const showDetail = ref(false)
const filterType = ref<string | null>(null)
const searchQuery = ref('')
const sortMode = ref<'chronological' | 'reverse' | 'alphabetical'>('chronological')

const typeColors: Record<string, string> = {
  combat: '#e74c3c',
  discovery: '#2ecc71',
  dialogue: '#3498db',
  travel: '#f39c12',
  rest: '#9b59b6',
  quest: '#1abc9c',
  other: '#95a5a6',
}

const typeIcons: Record<string, string> = {
  combat: '\u2694',
  discovery: '\uD83D\uDD0D',
  dialogue: '\uD83D\uDCAC',
  travel: '\uD83D\uDEE4\uFE0F',
  rest: '\uD83C\uDFD4\uFE0F',
  quest: '\uD83C\uDFF0',
  other: '\uD83D\uDCCC',
}

const filteredEvents = computed(() => {
  const query = searchQuery.value.trim().toLowerCase()
  let events = filterType.value
    ? timelineStore.events.filter((e) => e.event_type === filterType.value)
    : timelineStore.events

  if (query) {
    events = events.filter((event) => {
      const haystack = [
        event.title,
        event.description,
        event.speaker_name,
        event.temporal_entities.join(' '),
        event.location_entities.join(' '),
        event.characters.join(' '),
        event.event_type,
      ]
        .filter(Boolean)
        .join(' ')
        .toLowerCase()

      return haystack.includes(query)
    })
  }

  return [...events].sort((a, b) => {
    if (sortMode.value === 'alphabetical') {
      return (a.title || '').localeCompare(b.title || '')
    }

    if (sortMode.value === 'reverse') {
      return (b.order ?? 0) - (a.order ?? 0)
    }

    return (a.order ?? 0) - (b.order ?? 0)
  })
})

const uniqueTypes = computed(() => {
  const types = new Set(timelineStore.events.map((e) => e.event_type))
  return Array.from(types)
})

function openDetail(event: TimelineEventOut) {
  selectedEvent.value = event
  showDetail.value = true
}

function closeDetail() {
  showDetail.value = false
  selectedEvent.value = null
}

async function handleGenerate() {
  await timelineStore.generateEvents()
}

async function handleClear() {
  await timelineStore.clearEvents()
}

async function handleDeleteSelected() {
  if (!selectedEvent.value) return
  await timelineStore.removeEvent(selectedEvent.value.id)
  closeDetail()
}

function goBack() {
  router.push({ name: 'home' })
}

function formatTimestamp(seconds: number): string | null {
  if (!Number.isFinite(seconds) || seconds <= 0) return null
  const hours = Math.floor(seconds / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  const secs = Math.floor(seconds % 60)
  return `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${String(secs).padStart(2, '0')}`
}

function eventDisplayTime(event: TimelineEventOut): string {
  return event.display_time ?? formatTimestamp(event.timestamp) ?? '—'
}

onMounted(() => {
  timelineStore.fetchEvents()
})
</script>

<template>
  <div class="timeline-page">
    <div class="timeline-shell">
      <header class="timeline-header">
        <div class="title-group">
          <button class="back-btn" @click="goBack">← Back to Dashboard</button>
          <div>
            <p class="eyebrow">Session Story</p>
            <h1>Interactive Timeline</h1>
          </div>
        </div>
        <div class="header-actions">
          <button
            class="btn btn-primary"
            :disabled="timelineStore.generating"
            @click="handleGenerate"
          >
            {{ timelineStore.generating ? 'Generating...' : 'Generate Events' }}
          </button>
          <button
            class="btn btn-danger"
            :disabled="timelineStore.events.length === 0"
            @click="handleClear"
          >
            Clear All
          </button>
        </div>
      </header>

      <div v-if="timelineStore.error" class="error-banner">
        {{ timelineStore.error }}
      </div>

      <div v-if="timelineStore.loading" class="loading">Loading events...</div>

      <div v-else-if="timelineStore.events.length === 0" class="empty-state">
        <p>No timeline events yet.</p>
        <p>
          Record and transcribe a session, then click "Generate Events" to populate the timeline.
        </p>
      </div>

      <template v-else>
        <div class="controls-area">
          <div class="toolbar">
            <label class="search-field">
              <span class="search-icon">🔎</span>
              <input
                v-model="searchQuery"
                type="search"
                placeholder="Search events, speakers, places..."
              />
            </label>
            <label class="sort-field">
              <span>Sort</span>
              <select v-model="sortMode">
                <option value="chronological">Oldest first</option>
                <option value="reverse">Newest first</option>
                <option value="alphabetical">Alphabetical</option>
              </select>
            </label>
          </div>

          <div class="filter-bar">
            <span class="filter-label">Filter:</span>
            <button
              :class="['filter-btn', { active: filterType === null }]"
              @click="filterType = null"
            >
              All ({{ timelineStore.eventCount }})
            </button>
            <button
              v-for="type in uniqueTypes"
              :key="type"
              :class="['filter-btn', { active: filterType === type }]"
              @click="filterType = type"
            >
              {{ typeIcons[type] || '' }} {{ type }}
            </button>
            <span class="summary-pill">{{ filteredEvents.length }} events</span>
          </div>
        </div>

        <div class="events-scroll">
          <div v-if="filteredEvents.length === 0" class="empty-state compact">
            <p>No matching events found.</p>
            <p>Try another keyword or clear the active filter.</p>
          </div>

          <div v-else class="timeline-container">
            <div class="timeline-line"></div>
            <div
              v-for="event in filteredEvents"
              :key="event.id"
              class="timeline-event"
              :style="{ '--event-color': typeColors[event.event_type] || '#95a5a6' }"
              @click="openDetail(event)"
            >
              <div class="event-dot"></div>
              <div class="event-card">
                <div class="event-time">{{ eventDisplayTime(event) }}</div>
                <div
                  class="event-type-badge"
                  :style="{ background: typeColors[event.event_type] || '#95a5a6' }"
                >
                  {{ typeIcons[event.event_type] || '' }} {{ event.event_type }}
                </div>
                <h3 class="event-title">{{ event.title }}</h3>
                <p class="event-description">{{ event.description }}</p>
              </div>
            </div>
          </div>
        </div>
      </template>

      <div v-if="showDetail && selectedEvent" class="modal-overlay" @click.self="closeDetail">
        <div class="modal-content">
          <button class="modal-close" @click="closeDetail">&times;</button>
          <div
            class="modal-type-badge"
            :style="{ background: typeColors[selectedEvent.event_type] || '#95a5a6' }"
          >
            {{ selectedEvent.event_type }}
          </div>
          <div class="modal-time">{{ eventDisplayTime(selectedEvent) }}</div>
          <h2>{{ selectedEvent.title }}</h2>
          <p class="modal-description">{{ selectedEvent.description }}</p>
          <div class="modal-details">
            <div v-if="selectedEvent.speaker_name" class="detail-row">
              <strong>Speaker:</strong> {{ selectedEvent.speaker_name }}
            </div>
            <div v-if="selectedEvent.location_entities.length" class="detail-row">
              <strong>Locations:</strong> {{ selectedEvent.location_entities.join(', ') }}
            </div>
            <div v-if="selectedEvent.characters.length" class="detail-row">
              <strong>Characters:</strong> {{ selectedEvent.characters.join(', ') }}
            </div>
            <div v-if="selectedEvent.temporal_entities.length" class="detail-row">
              <strong>Time references:</strong> {{ selectedEvent.temporal_entities.join(', ') }}
            </div>
            <div class="detail-row"><strong>Order:</strong> #{{ selectedEvent.order }}</div>
          </div>
          <button class="btn btn-danger" @click="handleDeleteSelected">Delete Event</button>
        </div>
      </div>
    </div>
  </div>
</template>

<style src="@/assets/styles.css"></style>
<style scoped>
.timeline-page {
  height: 100vh;
  padding: 60px 1.25rem 1.25rem;
  background-image: url('/bg-texture.jpg');
  background-size: cover;
  background-position: center;
  background-attachment: fixed;
  background-color: rgba(36, 25, 7, 0.95);
  color: #392401;
  box-sizing: border-box;
  overflow: hidden;
}

.timeline-shell {
  max-width: 920px;
  height: 100%;
  margin: 0 auto;
  padding: 1.4rem;
  border-radius: 14px;
  background-color: rgba(163, 148, 95, 0.85);
  border: 1px solid rgba(105, 87, 16, 0.5);
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.timeline-header {
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

.eyebrow {
  margin: 0;
  color: #695710;
  font-size: 0.78rem;
  font-weight: 700;
  letter-spacing: 0.14em;
  text-transform: uppercase;
}

.timeline-header h1 {
  margin: 0;
  font-size: 1.6rem;
  font-weight: 700;
  text-align: left;
  padding-top: 0;
  color: #392401;
  font-family: 'MedievalSharp', cursive;
}

.header-actions {
  display: flex;
  gap: 0.6rem;
  flex-wrap: wrap;
}

.back-btn {
  align-self: flex-start;
  background-color: #b74d30;
  border: 1px solid #8e7513;
  color: white;
  padding: 0.5rem 0.85rem;
  border-radius: 10px;
  cursor: pointer;
  font-weight: 700;
  font-family: 'MedievalSharp', cursive;
  transition: all 0.2s ease;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
}

.back-btn:hover {
  background-color: #7e6f34;
  transform: translateY(-1px);
}

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

.btn-primary {
  background-color: rgba(53, 73, 94, 0.9);
  border-color: #4a575e;
  color: white;
}

.btn-primary:hover:not(:disabled) {
  background-color: #4a575e;
  transform: translateY(-1px);
}

.btn-primary:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.btn-danger {
  background-color: #b74d30;
  border-color: #8e7513;
  color: white;
}

.btn-danger:hover:not(:disabled) {
  background-color: #7e6f34;
  transform: translateY(-1px);
}

.btn-danger:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.error-banner {
  background: rgba(183, 77, 48, 0.2);
  border: 1px solid #b74d30;
  padding: 0.9rem 1rem;
  border-radius: 10px;
  margin-bottom: 1rem;
  color: #4c1a08;
  font-weight: 600;
}

.loading {
  text-align: center;
  padding: 2rem;
  color: #392401;
  font-family: 'MedievalSharp', cursive;
  font-size: 1.1rem;
}

.empty-state {
  text-align: center;
  padding: 2.2rem 1rem;
  background-color: rgba(241, 230, 180, 0.5);
  border-radius: 12px;
  border: 1px solid #695710;
  color: #392401;
}

.empty-state p {
  font-family: 'MedievalSharp', cursive;
  line-height: 1.6;
}

.empty-state.compact {
  margin-top: 1rem;
}

.toolbar {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin-bottom: 0.9rem;
  flex-wrap: wrap;
}

.controls-area {
  flex-shrink: 0;
  padding-bottom: 0.6rem;
  margin-bottom: 0.6rem;
  border-bottom: 1px solid rgba(105, 87, 16, 0.3);
}

.events-scroll {
  flex: 1;
  overflow-y: auto;
  min-height: 0;
}

.search-field,
.sort-field {
  display: flex;
  align-items: center;
  gap: 0.55rem;
  padding: 0.55rem 0.8rem;
  border-radius: 10px;
  border: 1px solid #695710;
  background-color: #f1e6b4;
}

.search-field {
  flex: 1;
  min-width: 240px;
}

.search-field input {
  border: none;
  outline: none;
  background: transparent;
  color: #392401;
  font-size: 0.95rem;
  width: 100%;
  font-family: 'MedievalSharp', cursive;
}

.search-field input::placeholder {
  color: #9e8a4e;
}

.sort-field span {
  color: #695710;
  font-weight: 700;
  font-size: 0.85rem;
  font-family: 'MedievalSharp', cursive;
}

.sort-field select {
  border: none;
  outline: none;
  background: transparent;
  color: #392401;
  font-size: 0.95rem;
  cursor: pointer;
  font-family: 'MedievalSharp', cursive;
}

.search-icon {
  font-size: 1rem;
}

.filter-bar {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.filter-label {
  font-weight: 700;
  color: #392401;
  font-size: 0.85rem;
  font-family: 'MedievalSharp', cursive;
}

.filter-btn {
  background-color: #f1e6b4;
  border: 1px solid #695710;
  color: #392401;
  padding: 0.35rem 0.65rem;
  border-radius: 999px;
  cursor: pointer;
  font-size: 0.82rem;
  font-family: 'MedievalSharp', cursive;
  font-weight: 600;
  transition: all 0.2s ease;
}

.filter-btn:hover {
  background-color: #e8d8a8;
}

.filter-btn.active {
  background-color: #b74d30;
  border-color: #8e7513;
  color: white;
}

.timeline-container {
  position: relative;
  padding-left: 2rem;
}

.timeline-line {
  position: absolute;
  left: 0.95rem;
  top: 0;
  bottom: 0;
  width: 2px;
  background: linear-gradient(180deg, #695710, rgba(105, 87, 16, 0.2));
  border-radius: 1px;
}

.timeline-event {
  position: relative;
  margin-bottom: 1rem;
  cursor: pointer;
}

.event-dot {
  position: absolute;
  left: -1.7rem;
  top: 0.95rem;
  width: 13px;
  height: 13px;
  border-radius: 50%;
  background: var(--event-color, #95a5a6);
  border: 2px solid #f1e6b4;
  z-index: 1;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.2);
}

.event-card {
  background-color: #f1e6b4;
  border: 1px solid #695710;
  border-radius: 10px;
  padding: 0.95rem 1rem;
  transition:
    transform 0.2s ease,
    box-shadow 0.2s ease;
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.12);
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.event-card:hover {
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
  transform: translateY(-1px);
}

.event-type-badge {
  display: inline-block;
  padding: 0.18rem 0.55rem;
  border-radius: 999px;
  font-size: 0.75rem;
  color: white;
  margin-bottom: 0.45rem;
  font-weight: 700;
  text-transform: capitalize;
  font-family: 'MedievalSharp', cursive;
}

.event-time {
  font-size: 0.75rem;
  color: #b45309;
  font-weight: 700;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  font-variant-numeric: tabular-nums;
  font-family: 'MedievalSharp', cursive;
}

.event-title {
  margin: 0;
  font-size: 1rem;
  font-weight: 700;
  color: #392401;
  font-family: 'MedievalSharp', cursive;
}

.event-description {
  margin: 0;
  font-size: 0.9rem;
  color: #4c3e06;
  line-height: 1.45;
  font-family: 'MedievalSharp', cursive;
}

.event-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 0.45rem;
}

.meta-item {
  font-size: 0.76rem;
  color: #695710;
  background-color: rgba(105, 87, 16, 0.12);
  padding: 0.16rem 0.44rem;
  border-radius: 999px;
  font-family: 'MedievalSharp', cursive;
  font-weight: 600;
}

.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.55);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  padding: 1rem;
}

.modal-content {
  background-color: rgba(163, 148, 95, 0.95);
  border: 1px solid #695710;
  border-radius: 14px;
  padding: 1.4rem;
  max-width: 520px;
  width: 100%;
  position: relative;
  color: #392401;
  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.35);
}

.modal-close {
  position: absolute;
  top: 0.6rem;
  right: 0.8rem;
  background: none;
  border: none;
  color: #392401;
  font-size: 1.5rem;
  cursor: pointer;
}

.modal-close:hover {
  color: #b74d30;
}

.modal-type-badge {
  display: inline-block;
  padding: 0.2rem 0.6rem;
  border-radius: 999px;
  font-size: 0.8rem;
  color: white;
  margin-bottom: 0.55rem;
  font-weight: 700;
  text-transform: capitalize;
  font-family: 'MedievalSharp', cursive;
}

.modal-time {
  font-size: 0.8rem;
  color: #b45309;
  font-weight: 700;
  margin-bottom: 0.45rem;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  font-variant-numeric: tabular-nums;
  font-family: 'MedievalSharp', cursive;
}

.modal-content h2 {
  margin: 0 0 0.55rem;
  text-align: left;
  color: #392401;
  font-family: 'MedievalSharp', cursive;
}

.modal-description {
  color: #4c3e06;
  line-height: 1.5;
  margin-bottom: 1rem;
  font-family: 'MedievalSharp', cursive;
}

.modal-details {
  margin-bottom: 1rem;
}

.detail-row {
  margin-bottom: 0.35rem;
  font-size: 0.9rem;
  color: #392401;
  font-family: 'MedievalSharp', cursive;
}

.detail-row strong {
  color: #695710;
}
</style>
