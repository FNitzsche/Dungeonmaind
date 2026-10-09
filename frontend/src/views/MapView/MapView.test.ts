import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import { reactive } from 'vue'

import { fetchMap, generateMap, parseMapData } from '@/api/mapAPI'
import { mapSample } from '@/fixtures/mapSample'
import { useMapStore } from '@/stores/map'
import { useSessionStore } from '@/stores/session'
import MapView from './MapView.vue'

const route = reactive<{ query: Record<string, string> }>({ query: {} })
const { push, replace } = vi.hoisted(() => ({ push: vi.fn(), replace: vi.fn() }))
vi.mock('vue-router', () => ({
  useRoute: () => route,
  useRouter: () => ({ push, replace }),
}))

vi.mock('cytoscape', async (importOriginal) => {
  const { default: cytoscape } = await importOriginal<{ default: typeof import('cytoscape') }>()
  return {
    default: (options: import('cytoscape').CytoscapeOptions) =>
      cytoscape({
        ...options,
        container: undefined,
        headless: true,
        layout: { name: 'preset' },
      }),
  }
})

const fetchMock = vi.fn<typeof fetch>()

beforeEach(() => {
  vi.stubGlobal('sessionStorage', { getItem: () => null })
  vi.stubGlobal('localStorage', { getItem: () => null })
  setActivePinia(createPinia())
  vi.stubGlobal('fetch', fetchMock)
  fetchMock.mockReset()
  route.query = {}
  push.mockReset()
  replace.mockReset().mockImplementation(({ query }) => {
    route.query = query
  })
})

afterEach(() => vi.unstubAllGlobals())

describe('map API boundary', () => {
  it('uses the dynamic backend URL, GET and bodyless POST', async () => {
    const session = useSessionStore()
    session.backendUrl = 'http://first.example'
    fetchMock.mockImplementation(async () => Response.json(mapSample))
    await expect(fetchMap()).resolves.toEqual(mapSample)
    session.backendUrl = 'http://second.example'
    await expect(generateMap()).resolves.toEqual(mapSample)
    expect(fetchMock.mock.calls).toEqual([
      ['http://first.example/map', { method: 'GET' }],
      ['http://second.example/map/generate', { method: 'POST' }],
    ])
  })

  it('accepts an empty map and rejects unfinalized or malformed schema', () => {
    expect(parseMapData({ nodes: [], edges: [], source_segment_count: 0 }).nodes).toEqual([])
    for (const data of [
      null,
      { map: mapSample },
      { ...mapSample, nodes: [{}] },
      { ...mapSample, edges: [{ ...mapSample.edges[0], relation: 'unknown' }] },
    ]) {
      expect(() => parseMapData(data)).toThrow('unsupported map format')
    }
  })

  it('reports unavailable endpoints and backend validation details', async () => {
    fetchMock.mockResolvedValueOnce(Response.json({ detail: 'Not Found' }, { status: 404 }))
    await expect(fetchMap()).rejects.toThrow('not available on this backend yet')
    fetchMock.mockResolvedValueOnce(
      Response.json({ detail: [{ msg: 'No transcript available' }] }, { status: 422 }),
    )
    await expect(generateMap()).rejects.toThrow('No transcript available')
  })

  it('reports network and non-JSON failures clearly', async () => {
    fetchMock.mockRejectedValueOnce(new TypeError('Failed to fetch'))
    await expect(fetchMap()).rejects.toThrow('Cannot reach the map backend')
    fetchMock.mockResolvedValueOnce(new Response('<html>error</html>', { status: 503 }))
    await expect(fetchMap()).rejects.toThrow('HTTP 503')
    fetchMock.mockResolvedValueOnce(new Response('invalid json'))
    await expect(fetchMap()).rejects.toThrow('unreadable map response')
  })
})

describe('map store requests', () => {
  it.each(['load', 'generate'] as const)(
    'prevents all overlapping requests during %s',
    async (action) => {
      let resolve!: (response: Response) => void
      fetchMock.mockReturnValue(
        new Promise<Response>((done) => {
          resolve = done
        }),
      )
      const store = useMapStore()
      const pending = action === 'load' ? store.loadMap() : store.generateMap()
      expect(store.loading).toBe(action === 'load')
      expect(store.generating).toBe(action === 'generate')
      await store.loadMap()
      await store.generateMap()
      expect(fetchMock).toHaveBeenCalledTimes(1)
      resolve(Response.json(mapSample))
      await pending
      expect(store.mapData).toEqual(mapSample)
      expect(store.loading || store.generating).toBe(false)
    },
  )

  it('clears error and busy state after retrying a failed generation', async () => {
    const store = useMapStore()
    fetchMock.mockResolvedValueOnce(
      Response.json({ detail: 'Extraction unavailable' }, { status: 500 }),
    )
    await store.generateMap()
    expect(store.error).toContain('Extraction unavailable')
    expect(store.generating).toBe(false)
    expect(store.mapData).toBeNull()
    fetchMock.mockResolvedValueOnce(Response.json(mapSample))
    await store.generateMap()
    expect(store.error).toBeNull()
    expect(store.mapData).toEqual(mapSample)
  })
})

describe('map page modes', () => {
  it('shows explicitly labeled sample data without requests or store contamination', async () => {
    route.query = { demo: 'sample' }
    const wrapper = mount(MapView)
    expect(wrapper.text()).toContain('Sample demo — invented data, not extracted session results.')
    expect(wrapper.text()).toContain('Willowbrook')
    expect(wrapper.get('.generate-button').attributes('disabled')).toBeDefined()
    expect(fetchMock).not.toHaveBeenCalled()
    expect(useMapStore().mapData).toBeNull()
    await wrapper.get('.back-button').trigger('click')
    expect(push).toHaveBeenCalledWith({ name: 'home' })
    wrapper.unmount()
  })

  it('loads on entry, never auto-generates, and switches explicitly between API and sample', async () => {
    fetchMock.mockImplementation(async () =>
      Response.json({ nodes: [], edges: [], source_segment_count: 0 }),
    )
    const wrapper = mount(MapView)
    expect(wrapper.text()).toContain('Loading the geographic map')
    await flushPromises()
    expect(wrapper.text()).toContain('No geographic map yet')
    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(fetchMock.mock.calls[0]?.[1]?.method).toBe('GET')
    await wrapper.get('.mode-panel button').trigger('click')
    expect(wrapper.text()).toContain('Sample map data')
    expect(fetchMock).toHaveBeenCalledTimes(1)
    await wrapper.get('.mode-panel button').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('No geographic map yet')
    expect(fetchMock).toHaveBeenCalledTimes(2)
    await wrapper.get('.generate-button').trigger('click')
    await flushPromises()
    expect(fetchMock.mock.calls[2]?.[1]?.method).toBe('POST')
    wrapper.unmount()
  })

  it('replaces selected sample data with real results and resets details on mode changes', async () => {
    route.query = { demo: 'sample' }
    const realData = {
      nodes: [
        {
          id: 'real-place',
          name: 'Real session place',
          mentions: 2,
          first_seen: 3601,
          last_seen: 3661,
        },
      ],
      edges: [],
      source_segment_count: 2,
    }
    fetchMock.mockImplementation(async () => Response.json(realData))
    const wrapper = mount(MapView)
    await wrapper.findAll('li button')[0]!.trigger('click')
    expect(wrapper.get('[aria-label="Selection details"]').text()).toContain('Willowbrook')
    await wrapper.get('.mode-panel button').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('Real session place')
    expect(wrapper.text()).not.toContain('Willowbrook')
    expect(wrapper.get('[aria-label="Selection details"]').text()).toContain('Select a location')
    expect(useMapStore().mapData).toEqual(realData)
    expect(fetchMock).toHaveBeenCalledTimes(1)
    await wrapper.get('.mode-panel button').trigger('click')
    expect(wrapper.text()).toContain('Willowbrook')
    expect(wrapper.text()).not.toContain('Real session place')
    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(useMapStore().mapData).toEqual(realData)
    wrapper.unmount()
  })

  it('shows backend errors without silently substituting the fixture', async () => {
    fetchMock.mockResolvedValue(Response.json({ detail: 'Not Found' }, { status: 404 }))
    const wrapper = mount(MapView)
    await flushPromises()
    expect(wrapper.get('[role="alert"]').text()).toContain('not available on this backend yet')
    expect(wrapper.text()).not.toContain('Willowbrook')
    expect(useMapStore().mapData).toBeNull()
    wrapper.unmount()
  })
})
