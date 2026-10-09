import type { MapData } from '@/api/mapAPI'

// SAMPLE ONLY: invented places and evidence, never extracted session results.
// Read separately by the view; never stored or sent to the API.
export const mapSample: MapData = {
  nodes: [
    { id: 'sample-village', name: 'Willowbrook', mentions: 3, first_seen: 10, last_seen: 120 },
    { id: 'sample-forest', name: 'Silverwood Forest', mentions: 2, first_seen: 30, last_seen: 120 },
    { id: 'sample-tower', name: 'Old Watchtower', mentions: 1, first_seen: 90, last_seen: 90 },
  ],
  edges: [
    {
      id: 'sample-north',
      source: 'sample-forest',
      target: 'sample-village',
      relation: 'north_of',
      evidence: 'Sample: Silverwood Forest lies north of Willowbrook.',
      timestamp: 30,
    },
    {
      id: 'sample-inside',
      source: 'sample-tower',
      target: 'sample-forest',
      relation: 'inside',
      evidence: 'Sample: The old watchtower stands inside Silverwood Forest.',
      timestamp: 90,
    },
    {
      id: 'sample-travel',
      source: 'sample-village',
      target: 'sample-forest',
      relation: 'travelled_to',
      evidence: 'Sample: The party travelled from Willowbrook to the forest.',
      timestamp: 120,
    },
  ],
  source_segment_count: 3,
}
