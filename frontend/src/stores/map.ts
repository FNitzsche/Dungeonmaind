import { ref } from 'vue'
import { defineStore } from 'pinia'

import { fetchMap, generateMap as generateMapRequest, type MapData } from '@/api/mapAPI'

export const useMapStore = defineStore('map', () => {
  const mapData = ref<MapData | null>(null)
  const loading = ref(false)
  const generating = ref(false)
  const error = ref<string | null>(null)

  async function loadMap(): Promise<void> {
    if (loading.value || generating.value) return

    loading.value = true
    error.value = null
    mapData.value = null

    try {
      mapData.value = await fetchMap()
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to load the geographic map.'
    } finally {
      loading.value = false
    }
  }

  async function generateMap(): Promise<void> {
    if (loading.value || generating.value) return

    generating.value = true
    error.value = null

    try {
      mapData.value = await generateMapRequest()
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to generate the geographic map.'
    } finally {
      generating.value = false
    }
  }

  return { mapData, loading, generating, error, loadMap, generateMap }
})
