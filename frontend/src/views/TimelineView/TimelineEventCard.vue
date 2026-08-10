<script setup lang="ts">
import { computed } from 'vue'

import type { TimelineEvent } from '@/api/timelineAPI'

const props = defineProps<{
  event: TimelineEvent
  isLast: boolean
  sessionDuration: number
}>()

const emit = defineEmits<{
  open: [event: TimelineEvent]
}>()

function formatTime(seconds: number): string {
  const safeSeconds = Math.max(0, Math.floor(seconds))
  const hours = Math.floor(safeSeconds / 3600)
  const minutes = Math.floor((safeSeconds % 3600) / 60)
  const remainingSeconds = safeSeconds % 60

  if (hours > 0) {
    return [hours, minutes, remainingSeconds]
      .map((value) => String(value).padStart(2, '0'))
      .join(':')
  }

  return [minutes, remainingSeconds]
    .map((value) => String(value).padStart(2, '0'))
    .join(':')
}

const categoryLabels: Record<TimelineEvent['category'], string> = {
  travel: 'Travel',
  combat: 'Combat',
  dialogue: 'Dialogue',
  discovery: 'Discovery',
  rest: 'Rest',
  quest: 'Quest',
  item: 'Item',
  other: 'Other',
}

const categoryIcons: Record<TimelineEvent['category'], string> = {
  travel: '🧭',
  combat: '⚔️',
  dialogue: '💬',
  discovery: '🔎',
  rest: '🔥',
  quest: '📜',
  item: '💎',
  other: '✦',
}

const timelineProgress = computed(() => {
  if (props.sessionDuration <= 0) {
    return 0
  }

  return Math.min(
    100,
    Math.max(
      0,
      (props.event.start_time / props.sessionDuration) * 100,
    ),
  )
})

const eventDuration = computed(() => {
  return Math.max(
    0,
    props.event.end_time - props.event.start_time,
  )
})
</script>

<template>
  <article class="timeline-row">
    <div class="timeline-time-column">
      <span class="timeline-time">
        {{ formatTime(event.start_time) }}
      </span>

      <span class="timeline-progress">
        {{ Math.round(timelineProgress) }}%
      </span>
    </div>

    <div class="timeline-marker-column" aria-hidden="true">
      <span
        class="timeline-marker"
        :class="`timeline-marker--${event.category}`"
      >
        {{ categoryIcons[event.category] }}
      </span>

      <span
        v-if="!isLast"
        class="timeline-line"
      ></span>
    </div>

    <button
      type="button"
      class="timeline-card"
      :aria-label="`Open details for ${event.title}`"
      @click="emit('open', event)"
    >
      <div class="timeline-card-header">
        <div class="timeline-title-group">
          <span
            class="category-badge"
            :class="`category-badge--${event.category}`"
          >
            {{ categoryLabels[event.category] }}
          </span>

          <h3>{{ event.title }}</h3>
        </div>

        <div class="timeline-time-details">
          <span class="timeline-duration">
            {{ formatTime(event.start_time) }}
            –
            {{ formatTime(event.end_time) }}
          </span>

          <span class="event-length">
            {{ Math.round(eventDuration) }} sec
          </span>
        </div>
      </div>

      <p class="timeline-description">
        {{ event.description }}
      </p>

      <div
        v-if="
          event.locations.length ||
          event.speakers.length ||
          event.temporal_entities.length
        "
        class="timeline-meta"
      >
        <span
          v-if="event.locations.length"
          class="meta-chip"
        >
          📍 {{ event.locations.join(', ') }}
        </span>

        <span
          v-if="event.speakers.length"
          class="meta-chip"
        >
          👥 {{ event.speakers.join(', ') }}
        </span>

        <span
          v-if="event.temporal_entities.length"
          class="meta-chip"
        >
          🕒 {{ event.temporal_entities.join(', ') }}
        </span>
      </div>

      <div class="timeline-card-footer">
        <span>
          {{ event.source_segments.length }}
          source segment{{
            event.source_segments.length === 1 ? '' : 's'
          }}
        </span>

        <span class="view-details">
          View details
          <span aria-hidden="true">→</span>
        </span>
      </div>
    </button>
  </article>
</template>

<style scoped>
.timeline-row {
  display: grid;
  grid-template-columns: 82px 58px minmax(0, 1fr);
  align-items: stretch;
}

.timeline-time-column {
  padding-top: 1.1rem;
  text-align: right;
}

.timeline-time {
  display: block;
  color: #422b0a;
  font-family: 'MedievalSharp', cursive;
  font-weight: 700;
}

.timeline-progress {
  display: block;
  margin-top: 0.25rem;
  color: #715c36;
  font-size: 0.72rem;
}

.timeline-marker-column {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
}

.timeline-marker {
  position: relative;
  z-index: 2;
  width: 44px;
  height: 44px;
  margin-top: 0.7rem;
  display: grid;
  place-items: center;
  border: 3px solid #f2e7bd;
  border-radius: 50%;
  background: #5b4724;
  box-shadow:
    0 3px 9px rgba(30, 18, 4, 0.38),
    inset 0 0 0 2px rgba(255, 255, 255, 0.12);
  font-size: 1.15rem;
}

.timeline-marker--combat {
  background: #7f2d25;
}

.timeline-marker--travel {
  background: #486744;
}

.timeline-marker--discovery {
  background: #3f6272;
}

.timeline-marker--rest {
  background: #654879;
}

.timeline-marker--quest {
  background: #805a18;
}

.timeline-marker--item {
  background: #796515;
}

.timeline-marker--dialogue {
  background: #595168;
}

.timeline-line {
  position: absolute;
  top: 50px;
  bottom: -14px;
  width: 4px;
  border-radius: 999px;
  background:
    linear-gradient(
      to bottom,
      #714b20,
      #bd9b58
    );
}

.timeline-card {
  width: 100%;
  margin: 0 0 1.3rem;
  padding: 1.25rem;
  border: 1px solid rgba(77, 48, 10, 0.42);
  border-radius: 15px;
  background:
    linear-gradient(
      135deg,
      rgba(248, 236, 191, 0.98),
      rgba(204, 178, 110, 0.98)
    );
  color: #382407;
  text-align: left;
  cursor: pointer;
  box-shadow: 0 6px 18px rgba(36, 20, 3, 0.2);
  transition:
    transform 0.2s ease,
    box-shadow 0.2s ease,
    border-color 0.2s ease;
}

.timeline-card:hover {
  transform: translateY(-3px);
  border-color: rgba(101, 52, 19, 0.75);
  box-shadow: 0 11px 25px rgba(36, 20, 3, 0.3);
}

.timeline-card:focus-visible {
  outline: 3px solid #47270e;
  outline-offset: 3px;
}

.timeline-card-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 1rem;
}

.timeline-title-group {
  min-width: 0;
}

.timeline-card h3 {
  margin: 0.55rem 0 0;
  color: #382306;
  font-family: 'MedievalSharp', cursive;
  font-size: 1.35rem;
}

.category-badge {
  display: inline-flex;
  padding: 0.25rem 0.68rem;
  border-radius: 999px;
  color: white;
  background: #66512d;
  font-size: 0.74rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.06em;
}

.category-badge--combat {
  background: #8a2e24;
}

.category-badge--travel {
  background: #496844;
}

.category-badge--discovery {
  background: #416374;
}

.category-badge--rest {
  background: #6a4b80;
}

.category-badge--quest {
  background: #875f18;
}

.category-badge--item {
  background: #806b15;
}

.category-badge--dialogue {
  background: #5b526e;
}

.timeline-time-details {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 0.25rem;
  white-space: nowrap;
}

.timeline-duration {
  color: #55401f;
  font-family: monospace;
  font-size: 0.84rem;
}

.event-length {
  color: #765f38;
  font-size: 0.75rem;
}

.timeline-description {
  margin: 1rem 0;
  line-height: 1.6;
}

.timeline-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 0.55rem;
}

.meta-chip {
  display: inline-flex;
  padding: 0.35rem 0.65rem;
  border: 1px solid rgba(79, 49, 10, 0.22);
  border-radius: 999px;
  background: rgba(255, 248, 218, 0.44);
  color: #5a4321;
  font-size: 0.84rem;
}

.timeline-card-footer {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  margin-top: 1rem;
  padding-top: 0.85rem;
  border-top: 1px solid rgba(83, 51, 10, 0.18);
  color: #6b5530;
  font-size: 0.82rem;
}

.view-details {
  color: #71301f;
  font-weight: 700;
}

@media (max-width: 680px) {
  .timeline-row {
    grid-template-columns: 48px minmax(0, 1fr);
  }

  .timeline-time-column {
    display: none;
  }

  .timeline-marker-column {
    grid-column: 1;
  }

  .timeline-card {
    grid-column: 2;
    padding: 1rem;
  }

  .timeline-card-header {
    flex-direction: column;
  }

  .timeline-time-details {
    align-items: flex-start;
  }

  .timeline-card-footer {
    flex-direction: column;
  }
}
</style>