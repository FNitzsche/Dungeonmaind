import type { MapEdge, MapGraphResponse, MapNode } from '@/api/mapAPI'
import type { TimelineEventOut } from '@/api/timelineAPI'

const MATCH_STOPWORDS = new Set(['the', 'a', 'an', 'of'])

/** Convert a place label into a stable map node id. */
export function placeToId(label: string): string {
  const slug = label
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
  return slug || 'unknown-place'
}

/** Compare place labels case-insensitively. */
export function placesMatch(a: string, b: string): boolean {
  return a.trim().toLowerCase() === b.trim().toLowerCase()
}

function matchingTokens(name: string): string[] {
  return name
    .trim()
    .toLowerCase()
    .replace(/-/g, ' ')
    .split(/\s+/)
    .filter((token) => token && !MATCH_STOPWORDS.has(token))
}

function isContiguousSubsequence(shorter: string[], longer: string[]): boolean {
  if (!shorter.length || shorter.length > longer.length) return false
  for (let index = 0; index <= longer.length - shorter.length; index += 1) {
    if (shorter.every((token, offset) => longer[index + offset] === token)) {
      return true
    }
  }
  return false
}

function editDistance(left: string, right: string): number {
  const previous = Array.from({ length: right.length + 1 }, (_, index) => index)
  for (let i = 1; i <= left.length; i += 1) {
    const current = [i]
    for (let j = 1; j <= right.length; j += 1) {
      const cost = left[i - 1] === right[j - 1] ? 0 : 1
      current[j] = Math.min(current[j - 1] + 1, previous[j] + 1, previous[j - 1] + cost)
    }
    for (let j = 0; j <= right.length; j += 1) previous[j] = current[j]
  }
  return previous[right.length]
}

function isNearDuplicate(left: string, right: string): boolean {
  const leftTokens = matchingTokens(left)
  const rightTokens = matchingTokens(right)
  if (!leftTokens.length || !rightTokens.length) return false
  if (leftTokens.join('\0') === rightTokens.join('\0')) return true
  if (isContiguousSubsequence(leftTokens, rightTokens)) return true
  if (isContiguousSubsequence(rightTokens, leftTokens)) return true
  if (
    leftTokens.length === 1 &&
    rightTokens.length === 1 &&
    Math.min(leftTokens[0].length, rightTokens[0].length) >= 5 &&
    editDistance(leftTokens[0], rightTokens[0]) <= 1
  ) {
    return true
  }
  return false
}

function specificity(name: string): [number, number] {
  return [matchingTokens(name).length, name.trim().length]
}

function isMoreSpecific(left: string, right: string): boolean {
  const leftScore = specificity(left)
  const rightScore = specificity(right)
  return (
    leftScore[0] > rightScore[0] || (leftScore[0] === rightScore[0] && leftScore[1] > rightScore[1])
  )
}

function pickCanonical(names: string[]): string {
  let best = names[0]
  for (const name of names.slice(1)) {
    if (isMoreSpecific(name, best)) best = name
  }
  return best
}

function uniqueLabels(labels: string[]): string[] {
  const seen = new Set<string>()
  const unique: string[] = []
  for (const raw of labels) {
    const label = raw.trim()
    if (!label) continue
    const key = label.toLowerCase()
    if (seen.has(key)) continue
    seen.add(key)
    unique.push(label)
  }
  return unique
}

function clusterPlaceNames(labels: string[]): string[][] {
  const unique = uniqueLabels(labels)
  if (unique.length === 0) return []

  const parent = new Map(unique.map((name) => [name.toLowerCase(), name.toLowerCase()]))

  const find = (key: string): string => {
    const current = parent.get(key) ?? key
    if (current !== key) {
      const root = find(current)
      parent.set(key, root)
      return root
    }
    return current
  }

  const union = (left: string, right: string) => {
    const leftRoot = find(left)
    const rightRoot = find(right)
    if (leftRoot !== rightRoot) parent.set(rightRoot, leftRoot)
  }

  const bySignature = new Map<string, string[]>()
  for (const name of unique) {
    const signature = matchingTokens(name).join('\0')
    if (!signature) continue
    const group = bySignature.get(signature) ?? []
    group.push(name.toLowerCase())
    bySignature.set(signature, group)
  }
  for (const group of bySignature.values()) {
    for (const key of group.slice(1)) union(group[0], key)
  }

  let changed = true
  while (changed) {
    changed = false
    for (const name of unique) {
      const nameRoot = find(name.toLowerCase())
      const candidateRoots: string[] = []
      for (const other of unique) {
        if (other.toLowerCase() === name.toLowerCase()) continue
        if (!isNearDuplicate(name, other)) continue
        if (!isMoreSpecific(other, name)) continue
        const root = find(other.toLowerCase())
        if (root === nameRoot) continue
        if (!candidateRoots.includes(root)) candidateRoots.push(root)
      }
      if (candidateRoots.length === 1) {
        union(name.toLowerCase(), candidateRoots[0])
        changed = true
      }
    }
  }

  const clustered = new Map<string, string[]>()
  for (const name of unique) {
    const root = find(name.toLowerCase())
    const group = clustered.get(root) ?? []
    group.push(name)
    clustered.set(root, group)
  }

  const ordered: string[][] = []
  const seenRoots = new Set<string>()
  for (const name of unique) {
    const root = find(name.toLowerCase())
    if (seenRoots.has(root)) continue
    seenRoots.add(root)
    ordered.push(clustered.get(root) ?? [name])
  }
  return ordered
}

/** True when a raw location string belongs to a map node (canonical name or alias). */
export function locationBelongsToNode(location: string, node: MapNode): boolean {
  if (placesMatch(location, node.label)) return true
  return (node.aliases ?? []).some((alias) => placesMatch(location, alias))
}

const EDGE_TYPE_RANK: Record<MapEdge['type'], number> = {
  other: 0,
  traveled: 1,
  near: 2,
  inside: 3,
  north_of: 4,
}

/** Infer a map-edge type from event wording until the real linker exists. */
export function inferEdgeType(
  event: Pick<TimelineEventOut, 'title' | 'description' | 'event_type'>,
): MapEdge['type'] {
  const text = `${event.title} ${event.description}`.toLowerCase()
  if (
    /\b(?:north of|south of|east of|west of|leading north|north towards|to the north)\b/.test(text)
  ) {
    return 'north_of'
  }
  if (/\b(?:inside|entered|into the|within)\b/.test(text)) return 'inside'
  if (/\b(?:near|beside|nearby|next to|close to)\b/.test(text)) return 'near'
  if (
    event.event_type === 'travel' ||
    /\b(?:traveled|travelled|journeyed|headed to|towards|traveled to)\b/.test(text)
  ) {
    return 'traveled'
  }
  return 'other'
}

function addEdge(
  edges: MapEdge[],
  byKey: Map<string, MapEdge>,
  from: string,
  to: string,
  type: MapEdge['type'],
) {
  if (!from || !to || from === to) return
  const key = `${from}->${to}`
  const existing = byKey.get(key)
  if (!existing) {
    const edge = { from, to, type }
    byKey.set(key, edge)
    edges.push(edge)
    return
  }
  if (EDGE_TYPE_RANK[type] > EDGE_TYPE_RANK[existing.type]) {
    existing.type = type
  }
}

/**
 * Build a schematic map from Release 2 timeline events until the map API exists.
 * Near-duplicate place names (e.g. 'the tavern' / 'Ye Olde Tavern') collapse to one node.
 * Colored links are inferred from event text (near / north of / inside / traveled).
 */
export function buildMapFromTimeline(
  events: TimelineEventOut[],
  sessionId = 'unsaved',
): MapGraphResponse {
  const allLabels = events.flatMap((event) => event.location_entities)
  const clusters = clusterPlaceNames(allLabels)
  const labelToCanonical = new Map<string, string>()
  const nodeById = new Map<string, MapNode>()

  for (const cluster of clusters) {
    const canonical = pickCanonical(cluster)
    const aliases = cluster.filter((name) => name.toLowerCase() !== canonical.toLowerCase())
    const id = placeToId(canonical)
    nodeById.set(id, aliases.length ? { id, label: canonical, aliases } : { id, label: canonical })
    for (const name of cluster) {
      labelToCanonical.set(name.toLowerCase(), canonical)
    }
  }

  const toNodeId = (label: string): string | null => {
    const canonical = labelToCanonical.get(label.toLowerCase()) ?? label
    const id = placeToId(canonical)
    return nodeById.has(id) ? id : null
  }

  const edges: MapEdge[] = []
  const byKey = new Map<string, MapEdge>()
  const sorted = [...events].sort((a, b) => (a.order ?? 0) - (b.order ?? 0))
  let lastPlaceId: string | null = null

  for (const event of sorted) {
    const placeIds = [
      ...new Set(
        event.location_entities
          .map((label) => toNodeId(label.trim()))
          .filter((id): id is string => Boolean(id)),
      ),
    ]
    if (placeIds.length === 0) continue

    const type = inferEdgeType(event)
    if (lastPlaceId) {
      addEdge(edges, byKey, lastPlaceId, placeIds[0], type)
    }
    for (let index = 0; index < placeIds.length - 1; index += 1) {
      addEdge(edges, byKey, placeIds[index], placeIds[index + 1], type)
    }
    lastPlaceId = placeIds[placeIds.length - 1]
  }

  return {
    session_id: sessionId,
    nodes: Array.from(nodeById.values()),
    edges,
  }
}
