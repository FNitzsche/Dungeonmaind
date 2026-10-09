import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import {
  fetchTimelineEvents,
  generateTimeline,
  type TimelineCategory,
  type TimelineEvent,
} from '@/api/timelineAPI'

export const useTimelineStore = defineStore('timeline', () => {
  const events = ref<TimelineEvent[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)
  const selectedCategory = ref<TimelineCategory | 'all'>('all')
  const searchQuery = ref('')

  const filteredEvents = computed(() => {
    const query = searchQuery.value.trim().toLowerCase()

    return events.value.filter((event) => {
      const categoryMatches =
        selectedCategory.value === 'all' ||
        event.category === selectedCategory.value

      const searchableText = [
        event.title,
        event.description,
        event.category,
        ...event.speakers,
        ...event.locations,
        ...event.temporal_entities,
      ]
        .join(' ')
        .toLowerCase()

      const searchMatches =
        query.length === 0 || searchableText.includes(query)

      return categoryMatches && searchMatches
    })
  })

  async function loadTimeline(): Promise<void> {
    loading.value = true
    error.value = null

    try {
      const response = await fetchTimelineEvents()
      events.value = response.events
    } catch (err) {
      error.value =
        err instanceof Error
          ? err.message
          : 'Failed to load the timeline.'
    } finally {
      loading.value = false
    }
  }

  async function regenerateTimeline(): Promise<void> {
    loading.value = true
    error.value = null

    try {
      const response = await generateTimeline()
      events.value = response.events
    } catch (err) {
      error.value =
        err instanceof Error
          ? err.message
          : 'Failed to generate the timeline.'
    } finally {
      loading.value = false
    }
  }

  function clearFilters(): void {
    selectedCategory.value = 'all'
    searchQuery.value = ''
  }

  return {
    events,
    loading,
    error,
    selectedCategory,
    searchQuery,
    filteredEvents,
    loadTimeline,
    regenerateTimeline,
    clearFilters,
  }
})