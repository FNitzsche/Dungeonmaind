<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import type {
  TimelineCategory,
  TimelineEvent,
} from '@/api/timelineAPI'
import { useTimelineStore } from '@/stores/timeline'
import TimelineEventCard from './TimelineEventCard.vue'
import TimelineEventModal from './TimelineEventModal.vue'

const router = useRouter()
const timelineStore = useTimelineStore()

const selectedEvent = ref<TimelineEvent | null>(null)

const categories: Array<{
  value: TimelineCategory | 'all'
  label: string
}> = [
  { value: 'all', label: 'All events' },
  { value: 'travel', label: 'Travel' },
  { value: 'combat', label: 'Combat' },
  { value: 'dialogue', label: 'Dialogue' },
  { value: 'discovery', label: 'Discovery' },
  { value: 'rest', label: 'Rest' },
  { value: 'quest', label: 'Quest' },
  { value: 'item', label: 'Items' },
  { value: 'other', label: 'Other' },
]

const sessionDuration = computed(() => {
  if (!timelineStore.events.length) {
    return 0
  }

  return Math.max(
    ...timelineStore.events.map((event) => event.end_time),
  )
})

const categoryTotals = computed(() => {
  const totals: Partial<Record<TimelineCategory, number>> = {}

  for (const event of timelineStore.events) {
    totals[event.category] =
      (totals[event.category] ?? 0) + 1
  }

  return totals
})

function formatDuration(seconds: number): string {
  const safeSeconds = Math.max(0, Math.floor(seconds))
  const hours = Math.floor(safeSeconds / 3600)
  const minutes = Math.floor((safeSeconds % 3600) / 60)
  const remainingSeconds = safeSeconds % 60

  if (hours > 0) {
    return `${hours}h ${minutes}m`
  }

  if (minutes > 0) {
    return `${minutes}m ${remainingSeconds}s`
  }

  return `${remainingSeconds}s`
}

onMounted(() => {
  timelineStore.loadTimeline()
})
</script>

<template>
  <div class="timeline-page">
    <header class="timeline-header">
      <button
        type="button"
        class="back-button"
        @click="router.push({ name: 'home' })"
      >
        ← Back to session
      </button>

      <div>
        <p class="eyebrow">Session Chronicle</p>
        <h1>Interactive Timeline</h1>
        <p class="header-description">
          Explore the important moments automatically extracted from
          the current Dungeons & Dragons session.
        </p>
      </div>

      <button
        type="button"
        class="generate-button"
        :disabled="timelineStore.loading"
        @click="timelineStore.regenerateTimeline"
      >
        {{
          timelineStore.loading
            ? 'Generating…'
            : 'Regenerate Timeline'
        }}
      </button>
    </header>

    <section class="summary-grid">
      <article class="summary-card">
        <span>Total events</span>
        <strong>{{ timelineStore.events.length }}</strong>
        <small>Important session moments</small>
      </article>
    
      <article class="summary-card">
        <span>Visible events</span>
        <strong>{{ timelineStore.filteredEvents.length }}</strong>
        <small>After search and filtering</small>
      </article>
    
      <article class="summary-card">
        <span>Session duration</span>
        <strong>{{ formatDuration(sessionDuration) }}</strong>
        <small>Based on the final event timestamp</small>
      </article>
    </section>

    <section class="timeline-controls">
      <label>
        Search timeline
        <input
          v-model="timelineStore.searchQuery"
          type="search"
          placeholder="Search title, location or speaker..."
        />
      </label>

      <label>
        Event category
        <select v-model="timelineStore.selectedCategory">
          <option
            v-for="category in categories"
            :key="category.value"
            :value="category.value"
          >
            {{ category.label }}
            {{
              category.value === 'all'
                ? `(${timelineStore.events.length})`
                : `(${categoryTotals[category.value] ?? 0})`
            }}
          </option>
        </select>
      </label>

      <button
        type="button"
        class="clear-button"
        @click="timelineStore.clearFilters"
      >
        Clear filters
      </button>
    </section>

    <p
      v-if="timelineStore.error"
      class="status-message status-message--error"
    >
      {{ timelineStore.error }}
    </p>

    <p
      v-else-if="timelineStore.loading"
      class="status-message"
    >
      Reading the session chronicle…
    </p>

    <section
      v-else-if="timelineStore.filteredEvents.length"
      class="timeline-list"
    >
      <TimelineEventCard
        v-for="(event, index) in timelineStore.filteredEvents"
        :key="event.id"
        :event="event"
        :session-duration="sessionDuration"
        :is-last="index === timelineStore.filteredEvents.length - 1"
        @open="selectedEvent = $event"
      />
    </section>

    <section v-else class="empty-state">
      <div class="empty-icon">📜</div>
      <h2>No timeline events found</h2>
      <p v-if="timelineStore.events.length">
        No events match the selected filters.
      </p>
      <p v-else>
        Record or upload a session, then regenerate the timeline.
      </p>

      <button
        type="button"
        class="generate-button"
        :disabled="timelineStore.loading"
        @click="timelineStore.regenerateTimeline"
      >
        {{
          timelineStore.loading
            ? 'Generating…'
            : 'Generate Timeline'
        }}
      </button>
    </section>

    <TimelineEventModal
      v-if="selectedEvent"
      :event="selectedEvent"
      @close="selectedEvent = null"
    />
  </div>
</template>

<style src="@/assets/styles.css"></style>

<style scoped>
.timeline-page {
  width: min(1050px, calc(100% - 2rem));
  margin: 2rem auto;
  padding: 1.5rem;
  box-sizing: border-box;
}

.timeline-header {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: center;
  gap: 1.5rem;
  padding: 1.5rem;
  border: 1px solid rgba(255, 239, 190, 0.25);
  border-radius: 18px;
  background: rgba(154, 124, 64, 0.94);
  box-shadow: 0 8px 30px rgba(26, 14, 2, 0.38);
}

.timeline-header h1 {
  padding: 0;
  margin: 0;
  text-align: left;
}

.eyebrow {
  margin: 0 0 0.3rem;
  color: #f6e7b7;
  font-family: 'MedievalSharp', cursive;
  text-transform: uppercase;
  letter-spacing: 0.12em;
}

.header-description {
  max-width: 620px;
  margin: 0.65rem 0 0;
  color: #fff5d4;
  line-height: 1.5;
}

.back-button,
.generate-button,
.clear-button {
  padding: 0.7rem 1rem;
  border: 1px solid #6a3b1d;
  border-radius: 10px;
  color: white;
  background: #8f3f28;
  cursor: pointer;
  font-family: 'MedievalSharp', cursive;
}

.back-button {
  background: rgba(53, 73, 94, 0.95);
}

.generate-button:disabled {
  opacity: 0.65;
  cursor: wait;
}

.back-button:hover,
.generate-button:hover,
.clear-button:hover {
  filter: brightness(1.08);
}

.back-button:focus-visible,
.generate-button:focus-visible,
.clear-button:focus-visible,
.timeline-controls input:focus-visible,
.timeline-controls select:focus-visible {
  outline: 3px solid #f2df9e;
  outline-offset: 2px;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 1rem;
  margin: 1.25rem 0;
}

.summary-card {
  padding: 1rem 1.2rem;
  border: 1px solid rgba(89, 56, 12, 0.35);
  border-radius: 12px;
  background: rgba(229, 207, 143, 0.94);
  color: #422b0a;
}

.summary-card span {
  display: block;
  font-size: 0.85rem;
}

.summary-card strong {
  display: block;
  margin-top: 0.35rem;
  font-family: 'MedievalSharp', cursive;
  font-size: 1.55rem;
}

.summary-card small {
  display: block;
  margin-top: 0.25rem;
  color: #715c36;
  font-size: 0.75rem;
}

.timeline-controls {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 220px auto;
  align-items: end;
  gap: 1rem;
  margin-bottom: 1.5rem;
  padding: 1rem;
  border-radius: 12px;
  background: rgba(163, 148, 95, 0.9);
}

.timeline-controls label {
  color: #392401;
  font-family: 'MedievalSharp', cursive;
}

.timeline-controls input,
.timeline-controls select {
  width: 100%;
  box-sizing: border-box;
  margin-top: 0.4rem;
  padding: 0.72rem;
  border: 1px solid #705820;
  border-radius: 8px;
  background: #f6edca;
  color: #3c280d;
}

.clear-button {
  background: #655538;
}

.timeline-list {
  padding: 1.5rem;
  border-radius: 18px;
  background: rgba(179, 153, 92, 0.55);
  box-shadow: inset 0 0 35px rgba(48, 27, 4, 0.18);
}

.status-message,
.empty-state {
  padding: 2rem;
  border-radius: 14px;
  text-align: center;
  color: #392401;
  background: rgba(224, 202, 139, 0.95);
}

.status-message--error {
  color: #7d1d18;
}

.empty-icon {
  font-size: 3rem;
}

.empty-state h2 {
  margin-top: 0.5rem;
}

@media (max-width: 760px) {
  .timeline-header {
    grid-template-columns: 1fr;
  }

  .summary-grid {
    grid-template-columns: 1fr;
  }

  .timeline-controls {
    grid-template-columns: 1fr;
  }

  .back-button,
  .generate-button,
  .clear-button {
    width: 100%;
  }
}
</style>