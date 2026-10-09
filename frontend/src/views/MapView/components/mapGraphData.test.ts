import { describe, expect, it } from 'vitest'
import cytoscape from 'cytoscape'
import { mapSample } from '@/fixtures/mapSample'
import { formatSessionTime, toGraphElements } from './mapGraph'

describe('map graph conversion', () => {
  it('preserves all contract fields and directed endpoints without mutating input', () => {
    const original = structuredClone(mapSample)
    const elements = toGraphElements(mapSample)
    expect(elements).toHaveLength(mapSample.nodes.length + mapSample.edges.length)
    for (const node of mapSample.nodes) {
      expect(elements).toContainEqual({ group: 'nodes', data: { ...node, label: node.name } })
    }
    for (const edge of mapSample.edges) {
      expect(elements).toContainEqual({
        group: 'edges',
        data: { ...edge, label: edge.relation.replace(/_/g, ' ') },
      })
    }
    const graph = cytoscape({ elements, headless: true })
    expect(graph.getElementById('sample-north').source().id()).toBe('sample-forest')
    expect(graph.getElementById('sample-north').target().id()).toBe('sample-village')
    graph.destroy()
    expect(mapSample).toEqual(original)
  })

  it('handles empty maps and omits dangling edges without inventing locations', () => {
    expect(toGraphElements({ nodes: [], edges: [], source_segment_count: 0 })).toEqual([])
    const data = {
      ...mapSample,
      nodes: mapSample.nodes.filter((node) => node.id === 'sample-village'),
    }
    expect(toGraphElements(data)).toHaveLength(1)
    expect(data.edges).toHaveLength(3)
  })
})

describe('session-relative timestamps', () => {
  it.each([
    [0, '00:00:00'],
    [90.9, '00:01:30'],
    [3661, '01:01:01'],
    [90000, '25:00:00'],
  ])('formats %s seconds as %s without wrapping at midnight', (seconds, expected) => {
    expect(formatSessionTime(Number(seconds))).toBe(expected)
  })
})
