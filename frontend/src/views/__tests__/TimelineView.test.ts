import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import TimelineView from '@/views/TimelineView.vue'
import { useMapStore } from '@/stores/map'
import { useSessionStore } from '@/stores/session'
import { useTimelineStore } from '@/stores/timeline'
import type { TimelineEventOut } from '@/api/timelineAPI'

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
  generateEvents: vi.fn(),
  deleteEvent: vi.fn(),
  clearEvents: vi.fn(),
}))

const EVENT = {
  id: 'e1',
  title: 'Arrival',
  description: 'The party reaches Neverwinter.',
  event_type: 'travel',
  temporal_entities: [],
  location_entities: ['Neverwinter'],
  characters: [],
} as unknown as TimelineEventOut

async function mountTimeline(options: { leader: boolean; events: TimelineEventOut[] }) {
  const sessionStore = useSessionStore()
  sessionStore.currentPlayer = {
    id: 'p1',
    role: options.leader ? 'leader' : 'player',
  } as typeof sessionStore.currentPlayer
  const timelineStore = useTimelineStore()
  // Keep the page from reloading the events over the ones set below.
  timelineStore.fetchEvents = vi.fn()
  timelineStore.events = options.events
  const wrapper = mount(TimelineView)
  await flushPromises()
  return wrapper
}

type Wrapper = Awaited<ReturnType<typeof mountTimeline>>

function buttonNamed(wrapper: Wrapper, name: RegExp) {
  return wrapper.findAll('button').find((button) => name.test(button.text()))
}

describe('TimelineView Generate Map button', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('builds the map for the current session when clicked', async () => {
    const wrapper = await mountTimeline({ leader: true, events: [EVENT] })
    const mapStore = useMapStore()
    mapStore.generateMap = vi.fn()

    await buttonNamed(wrapper, /^generate map$/i)?.trigger('click')

    expect(mapStore.generateMap).toHaveBeenCalledWith(useSessionStore().sessionId)
  })

  it('is hidden from players who are not the leader', async () => {
    const wrapper = await mountTimeline({ leader: false, events: [EVENT] })

    expect(buttonNamed(wrapper, /generate map/i)).toBeUndefined()
  })

  it('is disabled while there are no events to build a map from', async () => {
    const wrapper = await mountTimeline({ leader: true, events: [] })

    expect(buttonNamed(wrapper, /^generate map$/i)?.attributes('disabled')).toBeDefined()
  })
})
