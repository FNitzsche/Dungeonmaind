import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { enableAutoUnmount, mount } from '@vue/test-utils'
import type { Core } from 'cytoscape'
import { reactive } from 'vue'
import { mapSample } from '@/fixtures/mapSample'
import MapGraph from './MapGraph.vue'

// Real Cytoscape events and selection; jsdom has no canvas renderer.
const { instances } = vi.hoisted(() => ({ instances: [] as Core[] }))
vi.mock('cytoscape', async (importOriginal) => {
  const { default: cytoscape } = await importOriginal<{ default: typeof import('cytoscape') }>()
  return {
    default: (options: import('cytoscape').CytoscapeOptions) => {
      const graph = cytoscape({
        ...options,
        container: undefined,
        headless: true,
        styleEnabled: true,
        layout: { name: 'preset' },
      })
      instances.push(graph)
      return graph
    },
  }
})

enableAutoUnmount(afterEach)
const disconnect = vi.fn()
let resize: () => void
beforeEach(() => {
  instances.length = 0
  disconnect.mockClear()
  vi.stubGlobal(
    'ResizeObserver',
    class {
      constructor(callback: () => void) {
        resize = callback
      }
      observe = vi.fn()
      disconnect = disconnect
    },
  )
})
afterEach(() => vi.unstubAllGlobals())

describe('MapGraph', () => {
  it('synchronizes canvas selection, accessible buttons and details; clears on background and Escape', async () => {
    const wrapper = mount(MapGraph, { props: { data: mapSample } })
    const graph = instances[0]!
    graph.getElementById('sample-village').select()
    await wrapper.vm.$nextTick()
    const details = () => wrapper.get('[aria-label="Selection details"]').text()
    expect(details()).toContain('Willowbrook')
    expect(details()).toContain('Mentions3')
    expect(details()).toContain('00:00:10')
    expect(details()).toContain('00:02:00')
    expect(wrapper.get('[aria-pressed="true"]').text()).toContain('Willowbrook')
    const edgeButton = wrapper
      .findAll('li button')
      .find((button) => button.text().includes('north of'))!
    await edgeButton.trigger('click')
    expect(graph.getElementById('sample-north').selected()).toBe(true)
    expect(graph.getElementById('sample-village').selected()).toBe(false)
    expect(details()).toContain('SourceSilverwood Forest')
    expect(details()).toContain('TargetWillowbrook')
    expect(details()).toContain(mapSample.edges[0]!.evidence)
    expect(details()).toContain('00:00:30')
    graph.emit('tap')
    await wrapper.vm.$nextTick()
    expect(details()).toContain('Select a location')
    await edgeButton.trigger('click')
    await wrapper.trigger('keydown', { key: 'Escape' })
    expect(graph.elements(':selected')).toHaveLength(0)
    expect(details()).toContain('Select a location')
  })

  it('fits on request and resize, destroys stale instances on data replacement and unmount', async () => {
    const wrapper = mount(MapGraph, { props: { data: structuredClone(mapSample) } })
    const graph = instances[0]!
    const fit = vi.spyOn(graph, 'fit')
    const resized = vi.spyOn(graph, 'resize')
    await wrapper.get('.graph-toolbar button').trigger('click')
    expect(fit).toHaveBeenCalled()
    resize()
    expect(resized).toHaveBeenCalledTimes(2)
    graph.getElementById('sample-village').select()
    await wrapper.setProps({
      data: {
        nodes: [
          { id: 'real', name: 'Session place', mentions: 1, first_seen: 3601, last_seen: 3661 },
        ],
        edges: [],
        source_segment_count: 1,
      },
    })
    expect(graph.destroyed()).toBe(true)
    expect(disconnect).toHaveBeenCalledTimes(1)
    expect(wrapper.text()).not.toContain('Willowbrook')
    expect(wrapper.get('[aria-label="Selection details"]').text()).toContain('Select a location')
    const current = instances[1]!
    expect(current.nodes().map((node) => node.id())).toEqual(['real'])
    wrapper.unmount()
    expect(current.destroyed()).toBe(true)
    expect(disconnect).toHaveBeenCalledTimes(2)
  })

  it('handles empty maps and clears stale selection when locations disappear', async () => {
    const wrapper = mount(MapGraph, { props: { data: structuredClone(mapSample) } })
    const graph = instances[0]!
    graph.getElementById('sample-village').select()
    await wrapper.setProps({ data: { ...mapSample, nodes: [] } })
    expect(graph.destroyed()).toBe(true)
    expect(wrapper.text()).toContain('No locations to display.')
    expect(wrapper.get('.graph-toolbar button').attributes('disabled')).toBeDefined()
    expect(wrapper.text()).toContain('only shown in the relationship list')
    await wrapper.setProps({ data: { nodes: [], edges: [], source_segment_count: 0 } })
    expect(wrapper.text()).toContain('No geographic relationships found.')
    expect(instances).toHaveLength(1)
  })

  it('rebuilds when the same reactive map changes in place', async () => {
    const data = reactive(structuredClone(mapSample))
    const wrapper = mount(MapGraph, { props: { data } })
    const graph = instances[0]!
    graph.getElementById('sample-village').select()
    data.nodes[0]!.name = 'Updated place'
    await wrapper.vm.$nextTick()
    expect(graph.destroyed()).toBe(true)
    expect(instances[1]!.getElementById('sample-village').data('label')).toBe('Updated place')
    expect(wrapper.get('[aria-label="Selection details"]').text()).toContain('Select a location')
  })

  it('renders evidence as text and lets keyboard users select dangling edges', async () => {
    const edge = {
      ...mapSample.edges[0]!,
      evidence: '<img src=x onerror=alert(1)>',
      target: 'missing',
    }
    const wrapper = mount(MapGraph, { props: { data: { ...mapSample, edges: [edge] } } })
    const buttons = wrapper.findAll('li button')
    await buttons[buttons.length - 1]!.trigger('click')
    expect(wrapper.get('[aria-label="Selection details"]').text()).toContain('Targetmissing')
    expect(wrapper.text()).toContain(edge.evidence)
    expect(wrapper.find('img').exists()).toBe(false)
    await wrapper.findAll('.graph-toolbar button')[1]!.trigger('click')
    expect(wrapper.find('[aria-pressed="true"]').exists()).toBe(false)
  })
})
