import unittest

from langchain_core.documents import Document

from app.domain.models import TimelineEventType
from app.functions.llm.event_extractor import (
    build_timeline_events_from_transcription_documents,
    compute_display_time,
)


class TimelineEntityEventTests(unittest.TestCase):
    def test_builds_timeline_event_from_transcription_metadata(self):
        docs = [
            Document(
                page_content='Around noon, the party reached Silver Lake and found a hidden trail.',
                metadata={
                    'player_id': 'Poornesh Shiva',
                    'temporal_entities': 'Around noon',
                    'location_entities': 'Silver Lake',
                },
            )
        ]

        events = build_timeline_events_from_transcription_documents(docs)

        self.assertEqual(len(events), 1)
        self.assertNotIn(' at Silver Lake', events[0].title)
        self.assertNotIn('Around noon', events[0].title)
        self.assertEqual(events[0].temporal_entities, ['Around noon'])
        self.assertEqual(events[0].location_entities, ['Silver Lake'])
        self.assertEqual(events[0].event_type, TimelineEventType.travel)
        self.assertIn('Silver Lake', events[0].description)
        self.assertEqual(events[0].display_time, 'Noon')
        self.assertEqual(events[0].characters, ['Poornesh Shiva'])

    def test_builds_timeline_event_with_recording_timestamp(self):
        docs = [
            Document(
                page_content='Around midday, they discovered a rune shrine.',
                metadata={
                    'player_id': 'GM',
                    'temporal_entities': 'Around midday',
                    'location_entities': 'Anthem',
                    'start_time': 405.0,
                },
            )
        ]

        events = build_timeline_events_from_transcription_documents(docs)

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].display_time, '00:06:45')
        self.assertEqual(events[0].timestamp, 405.0)

    def test_compute_display_time_prefers_recording_timestamp(self):
        display_time = compute_display_time(['Midday'], text='Around midday', timestamp=1092.0)

        self.assertEqual(display_time, '00:18:12')


if __name__ == '__main__':
    unittest.main()
