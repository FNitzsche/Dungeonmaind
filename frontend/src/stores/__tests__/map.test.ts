import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import * as mapApi from '@/api/mapAPI'
import * as timelineApi from '@/api/timelineAPI'
import { useMapStore } from '@/stores/map'

vi.mock('@/api/mapAPI', () => ({
  getMap: vi.fn(),
  generateMap: vi.fn(),
  getPlaceEvents: vi.fn(),
}))

vi.mock('@/api/timelineAPI', () => ({
  listEvents: vi.fn(),
}))

const SESSION = 'session-1'

describe('map store apiStatus', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    setActivePinia(createPinia())
    // The timeline fallback runs whenever the map API call fails.
    vi.mocked(timelineApi.listEvents).mockResolvedValue({
      session_id: SESSION,
      events: [],
      total: 0,
    })
  })

  it('starts as unknown before anything has loaded', () => {
    expect(useMapStore().apiStatus).toBe('unknown')
  })

  it('is up when the map loads from the API', async () => {
    vi.mocked(mapApi.getMap).mockResolvedValue({ session_id: SESSION, nodes: [], edges: [] })
    const store = useMapStore()

    await store.fetchMap(SESSION)

    expect(store.apiStatus).toBe('up')
    expect(store.dataSource).toBe('api')
  })

  it('is up when the API answers 404 because no map was generated yet', async () => {
    vi.mocked(mapApi.getMap).mockRejectedValue(new Error('HTTP 404'))
    const store = useMapStore()

    await store.fetchMap(SESSION)

    expect(store.apiStatus).toBe('up')
    expect(store.dataSource).toBe('timeline')
  })

  it('is down when the API cannot be reached', async () => {
    vi.mocked(mapApi.getMap).mockRejectedValue(new TypeError('Failed to fetch'))
    const store = useMapStore()

    await store.fetchMap(SESSION)

    expect(store.apiStatus).toBe('down')
    expect(store.dataSource).toBe('timeline')
  })
})
