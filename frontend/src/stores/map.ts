import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import * as mapApi from '@/api/mapAPI'
import type { MapEdge, MapEdgeType, MapNode } from '@/api/mapAPI'
import { useSessionStore } from '@/stores/session'
import { useTimelineStore } from '@/stores/timeline'
import { buildMapFromTimeline, locationBelongsToNode, placeToId } from '@/utils/mapFromTimeline'

/** Whether the map graph came from the backend API or timeline fallback. */
export type MapDataSource = 'api' | 'timeline'

/**
 * Whether the map API could be reached on the last load. A 404 ("no map saved
 * yet") still counts as `up`: the server answered, it just has nothing to show.
 */
export type MapApiStatus = 'unknown' | 'up' | 'down'

/**
 * Map store – loads session place graph and selected-place event links.
 * Falls back to timeline location_entities when the map API is unavailable.
 */
export const useMapStore = defineStore('map', () => {
  const nodes = ref<MapNode[]>([])
  const edges = ref<MapEdge[]>([])
  const sessionId = ref('unsaved')
  const loading = ref(false)
  const generating = ref(false)
  const saving = ref(false)
  const error = ref<string | null>(null)
  const dataSource = ref<MapDataSource>('timeline')
  const apiStatus = ref<MapApiStatus>('unknown')
  const selectedPlaceId = ref<string | null>(null)
  const selectedEventIds = ref<string[]>([])

  const nodeCount = computed(() => nodes.value.length)
  const edgeCount = computed(() => edges.value.length)

  const selectedNode = computed(
    () => nodes.value.find((node) => node.id === selectedPlaceId.value) ?? null,
  )

  function resolveSessionId(forSessionId?: string) {
    return forSessionId ?? useSessionStore().sessionId
  }

  /**
   * Load map data for a session. Uses backend API when available, otherwise timeline events.
   */
  async function fetchMap(forSessionId?: string) {
    const id = resolveSessionId(forSessionId)
    loading.value = true
    error.value = null
    if (sessionId.value !== id) {
      // Another session: never keep showing the previous session's places.
      nodes.value = []
      edges.value = []
      clearSelection()
    }
    sessionId.value = id

    try {
      const response = await mapApi.getMap(id)
      // Ignore an answer that arrives after the user switched to another session.
      if (sessionId.value !== id) return
      nodes.value = response.nodes ?? []
      edges.value = response.edges ?? []
      dataSource.value = 'api'
      apiStatus.value = 'up'
    } catch (apiError) {
      if (sessionId.value !== id) return
      const message = apiError instanceof Error ? apiError.message : 'Map API unavailable'
      apiStatus.value = message.includes('404') ? 'up' : 'down'
      const timelineStore = useTimelineStore()
      const timelineIsForOtherSession = timelineStore.sessionId !== id
      if (
        timelineIsForOtherSession ||
        (timelineStore.events.length === 0 && !timelineStore.loading)
      ) {
        await timelineStore.fetchEvents(id)
      }

      const fallback = buildMapFromTimeline(timelineStore.events, id)
      nodes.value = fallback.nodes
      edges.value = fallback.edges
      dataSource.value = 'timeline'

      if (fallback.nodes.length === 0) {
        error.value =
          message.includes('404') || message.includes('HTTP 404')
            ? null
            : `Map API unavailable — showing timeline places when available. (${message})`
      }
    } finally {
      loading.value = false
    }
  }

  /**
   * Ask the backend to build and save the map, then reload it.
   * @param forSessionId - Optional override. Defaults to the session store key.
   */
  async function generateMap(forSessionId?: string) {
    const id = resolveSessionId(forSessionId)
    if (generating.value) return
    if (!useSessionStore().isLeader) {
      error.value = 'Only the leader can generate the map'
      return
    }
    generating.value = true
    error.value = null
    try {
      await mapApi.generateMap(id)
      await fetchMap(id)
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to generate map'
    } finally {
      generating.value = false
    }
  }

  /** Select a place node and load linked timeline events. */
  async function selectPlace(placeId: string | null) {
    selectedPlaceId.value = placeId
    selectedEventIds.value = []

    if (!placeId) return

    const node = nodes.value.find((item) => item.id === placeId)
    if (!node) return

    if (dataSource.value === 'api') {
      try {
        const response = await mapApi.getPlaceEvents(sessionId.value, placeId)
        selectedEventIds.value = response.event_ids ?? []
        return
      } catch {
        // Fall through to timeline-based lookup.
      }
    }

    const timelineStore = useTimelineStore()
    selectedEventIds.value = timelineStore.events
      .filter((event) =>
        event.location_entities.some((location) => locationBelongsToNode(location, node)),
      )
      .map((event) => event.id)
  }

  /** Resolve a place query string to a node id, if it matches a label. */
  function resolvePlaceQuery(placeQuery: string | null | undefined): string | null {
    if (!placeQuery?.trim()) return null
    const query = placeQuery.trim()
    const byId = nodes.value.find((node) => node.id === query)
    if (byId) return byId.id
    const byLabel = nodes.value.find((node) => locationBelongsToNode(query, node))
    return byLabel?.id ?? placeToId(query)
  }

  function clearSelection() {
    selectedPlaceId.value = null
    selectedEventIds.value = []
  }

  async function persistEdit(run: () => Promise<void>) {
    if (!useSessionStore().isLeader) {
      error.value = 'Only the leader can edit the map'
      return
    }
    saving.value = true
    error.value = null
    try {
      await run()
      await fetchMap()
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to save map edit'
      throw err
    } finally {
      saving.value = false
    }
  }

  async function renamePlace(locationId: string, canonicalName: string) {
    await persistEdit(() => mapApi.renamePlace(sessionId.value, locationId, canonicalName))
  }

  async function mergePlaces(sourceLocationIds: string[], targetLocationId: string) {
    await persistEdit(() =>
      mapApi.mergePlaces(sessionId.value, sourceLocationIds, targetLocationId),
    )
    if (sourceLocationIds.includes(selectedPlaceId.value ?? '')) {
      await selectPlace(targetLocationId)
    }
  }

  async function splitPlace(sourceLocationId: string, canonicalName: string, eventIds: string[]) {
    await persistEdit(() =>
      mapApi.splitPlace(sessionId.value, sourceLocationId, canonicalName, eventIds),
    )
  }

  async function connectPlaces(fromLocationId: string, toLocationId: string, type?: MapEdgeType) {
    await persistEdit(() =>
      mapApi.connectPlaces(sessionId.value, fromLocationId, toLocationId, type),
    )
  }

  async function disconnectPlaces(
    fromLocationId: string,
    toLocationId: string,
    type?: MapEdgeType,
  ) {
    await persistEdit(() =>
      mapApi.disconnectPlaces(sessionId.value, fromLocationId, toLocationId, type),
    )
  }

  return {
    nodes,
    edges,
    sessionId,
    loading,
    generating,
    saving,
    error,
    dataSource,
    apiStatus,
    selectedPlaceId,
    selectedEventIds,
    nodeCount,
    edgeCount,
    selectedNode,
    fetchMap,
    generateMap,
    selectPlace,
    resolvePlaceQuery,
    clearSelection,
    renamePlace,
    mergePlaces,
    splitPlace,
    connectPlaces,
    disconnectPlaces,
  }
})
