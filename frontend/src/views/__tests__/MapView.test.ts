import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { mount, flushPromises } from '@vue/test-utils'
import MapView from '@/views/MapView.vue'
import { useMapStore } from '@/stores/map'
import { useSessionStore } from '@/stores/session'
import { useTimelineStore } from '@/stores/timeline'

vi.mock('vue-router', () => ({
  useRoute: () => ({ query: {} }),
  useRouter: () => ({ push: vi.fn() }),
}))

vi.mock('@/api/mapAPI', () => ({
  getMap: vi.fn(),
  generateMap: vi.fn(),
  getPlaceEvents: vi.fn(),
}))

vi.mock('@/api/timelineAPI', () => ({
  listEvents: vi.fn(),
}))

async function mountAsLeader(places: string[]) {
  const sessionStore = useSessionStore()
  sessionStore.currentPlayer = { id: 'p1', role: 'leader' } as typeof sessionStore.currentPlayer
  const mapStore = useMapStore()
  // Keep the page from reloading the map over the places set below.
  mapStore.fetchMap = vi.fn()
  mapStore.nodes = places.map((label) => ({ id: label, label }))
  const wrapper = mount(MapView, { global: { stubs: { MapEditPanel: true } } })
  await flushPromises()
  return wrapper
}

type Wrapper = Awaited<ReturnType<typeof mountAsLeader>>

function buttonNamed(wrapper: Wrapper, name: RegExp) {
  return wrapper.findAll('button').find((button) => name.test(button.text()))
}

function generateButton(wrapper: Wrapper) {
  return buttonNamed(wrapper, /^(re)?generate map$/i)
}

describe('MapView generate button', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('says "Generate map" while the map has no places yet', async () => {
    const wrapper = await mountAsLeader([])

    expect(generateButton(wrapper)?.text()).toBe('Generate map')
  })

  it('says "Regenerate map" once the map already has places', async () => {
    const wrapper = await mountAsLeader(['Neverwinter', 'Phandalin'])

    expect(generateButton(wrapper)?.text()).toBe('Regenerate map')
  })
})

describe('MapView Generate Events button', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('generates the events and then rebuilds the map', async () => {
    const wrapper = await mountAsLeader(['Neverwinter'])
    const timelineStore = useTimelineStore()
    const mapStore = useMapStore()
    const order: string[] = []
    timelineStore.generateEvents = vi.fn(async () => {
      order.push('events')
      return { session_id: 'unsaved', events_generated: 1, events: [] }
    })
    mapStore.generateMap = vi.fn(async () => {
      order.push('map')
    })

    await buttonNamed(wrapper, /^generate events$/i)?.trigger('click')
    await flushPromises()

    expect(order).toEqual(['events', 'map'])
  })

  it('leaves the map alone when generating the events fails', async () => {
    const wrapper = await mountAsLeader(['Neverwinter'])
    const timelineStore = useTimelineStore()
    const mapStore = useMapStore()
    timelineStore.generateEvents = vi.fn(async () => null)
    mapStore.generateMap = vi.fn()

    await buttonNamed(wrapper, /^generate events$/i)?.trigger('click')
    await flushPromises()

    expect(mapStore.generateMap).not.toHaveBeenCalled()
  })
})
