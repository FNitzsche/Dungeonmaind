<script setup lang="ts">
import type { TimelineEvent } from '@/api/timelineAPI'

defineProps<{
  event: TimelineEvent
}>()

const emit = defineEmits<{
  close: []
}>()

function formatTime(seconds: number): string {
  const value = Math.max(0, Math.floor(seconds))
  const hours = Math.floor(value / 3600)
  const minutes = Math.floor((value % 3600) / 60)
  const secs = value % 60

  return [hours, minutes, secs]
    .map((part) => String(part).padStart(2, '0'))
    .join(':')
}
</script>

<template>
  <Teleport to="body">
    <div
      class="dnd-modal-overlay"
      @click.self="emit('close')"
    >
      <section
        class="dnd-event-modal"
        role="dialog"
        aria-modal="true"
        :aria-label="event.title"
      >
        <button
          type="button"
          class="dnd-modal-close"
          aria-label="Close"
          @click="emit('close')"
        >
          ×
        </button>

        <p class="dnd-modal-category">
          {{ event.category }}
        </p>

        <h2>{{ event.title }}</h2>

        <p class="dnd-modal-time">
          {{ formatTime(event.start_time) }}
          –
          {{ formatTime(event.end_time) }}
        </p>

        <p class="dnd-modal-description">
          {{ event.description }}
        </p>

        <div class="dnd-details-grid">
          <div>
            <h3>Locations</h3>
            <p>
              {{
                event.locations.length
                  ? event.locations.join(', ')
                  : 'None detected'
              }}
            </p>
          </div>

          <div>
            <h3>Speakers</h3>
            <p>
              {{
                event.speakers.length
                  ? event.speakers.join(', ')
                  : 'Unknown'
              }}
            </p>
          </div>

          <div>
            <h3>Temporal expressions</h3>
            <p>
              {{
                event.temporal_entities.length
                  ? event.temporal_entities.join(', ')
                  : 'None detected'
              }}
            </p>
          </div>

          <div>
            <h3>Duration</h3>
            <p>
              {{ Math.max(0, Math.round(event.end_time - event.start_time)) }}
              seconds
            </p>
          </div>
        </div>

        <section
          v-if="event.source_segments.length"
          class="dnd-source-section"
        >
          <h3>Source transcription</h3>

          <article
            v-for="(segment, index) in event.source_segments"
            :key="`${event.id}-${index}`"
            class="dnd-source-segment"
          >
            <div class="dnd-source-header">
              <strong>{{ segment.speaker }}</strong>

              <span>
                {{ formatTime(segment.start_time) }}
                –
                {{ formatTime(segment.end_time) }}
              </span>
            </div>

            <p>{{ segment.text }}</p>
          </article>
        </section>
      </section>
    </div>
  </Teleport>
</template>

<style>
.dnd-modal-overlay {
  position: fixed;
  inset: 0;
  z-index: 99999;
  display: grid;
  place-items: center;
  box-sizing: border-box;
  padding: 20px;
  overflow-y: auto;
  background: rgba(20, 12, 3, 0.78);
}

.dnd-event-modal {
  position: relative;
  width: min(760px, 100%);
  max-height: 88vh;
  box-sizing: border-box;
  overflow-y: auto;
  padding: 32px;
  border: 1px solid #765821;
  border-radius: 16px;
  background: #e5cf8f;
  color: #2f210e;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.6);
}

.dnd-event-modal,
.dnd-event-modal h2,
.dnd-event-modal h3,
.dnd-event-modal p,
.dnd-event-modal span,
.dnd-event-modal strong {
  color: #2f210e;
}

.dnd-modal-close {
  position: absolute;
  top: 10px;
  right: 14px;
  border: 0;
  background: transparent;
  color: #3b210c;
  cursor: pointer;
  font-size: 32px;
}

.dnd-modal-category {
  margin: 0;
  font-weight: 800;
  text-transform: uppercase;
  letter-spacing: 0.1em;
}

.dnd-event-modal h2 {
  margin: 8px 45px 8px 0;
  text-align: left;
  font-size: 28px;
}

.dnd-modal-time {
  margin: 0 0 16px;
  font-family: monospace;
}

.dnd-modal-description {
  line-height: 1.6;
}

.dnd-details-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  margin: 24px 0;
}

.dnd-details-grid > div {
  padding: 14px;
  border: 1px solid rgba(78, 49, 10, 0.3);
  border-radius: 10px;
  background: #f4e8bd;
}

.dnd-details-grid h3,
.dnd-source-section h3 {
  margin: 0 0 6px;
}

.dnd-details-grid p {
  margin: 0;
}

.dnd-source-section {
  margin-top: 24px;
}

.dnd-source-segment {
  margin-top: 10px;
  padding: 14px;
  border-left: 4px solid #765021;
  border-radius: 8px;
  background: #f8edc9;
}

.dnd-source-header {
  display: flex;
  justify-content: space-between;
  gap: 16px;
}

.dnd-source-segment p {
  margin: 10px 0 0;
  line-height: 1.5;
}

@media (max-width: 600px) {
  .dnd-event-modal {
    padding: 22px;
  }

  .dnd-details-grid {
    grid-template-columns: 1fr;
  }

  .dnd-source-header {
    flex-direction: column;
    gap: 4px;
  }
}
</style>