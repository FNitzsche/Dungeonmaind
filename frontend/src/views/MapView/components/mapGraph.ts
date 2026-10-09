import type { ElementDefinition } from 'cytoscape'
import type { MapData } from '@/api/mapAPI'

/** Preserve contract fields; Cytoscape needs labels but no inferred relationships. */
export function toGraphElements(data: MapData): ElementDefinition[] {
  const nodeIds = new Set(data.nodes.map((node) => node.id))
  return [
    ...data.nodes.map((node) => ({ group: 'nodes' as const, data: { ...node, label: node.name } })),
    ...data.edges
      // Dangling edges cannot be rendered. They remain available in the textual list.
      .filter((edge) => nodeIds.has(edge.source) && nodeIds.has(edge.target))
      .map((edge) => ({
        group: 'edges' as const,
        data: { ...edge, label: edge.relation.replace(/_/g, ' ') },
      })),
  ]
}

/** Elapsed session time, including hours beyond 24; never a wall-clock Date. */
export function formatSessionTime(seconds: number): string {
  const elapsed = Math.floor(seconds)
  const hours = Math.floor(elapsed / 3600)
  const minutes = Math.floor((elapsed % 3600) / 60)
  const remainder = elapsed % 60
  return `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${remainder.toString().padStart(2, '0')}`
}
