import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { mount, flushPromises } from '@vue/test-utils'
import MapView from '@/views/MapView.vue'
import { useMapStore } from '@/stores/map'
import { useSessionStore } from '@/stores/session'

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

function generateButton(wrapper: Awaited<ReturnType<typeof mountAsLeader>>) {
  return wrapper.findAll('button').find((button) => /generate/i.test(button.text()))
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
