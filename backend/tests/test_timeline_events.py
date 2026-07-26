import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.core.config import settings
from app.functions.llm.event_extractor import build_timeline_events_from_transcription_documents


class TimelineEventExtractorTests(unittest.TestCase):
    def test_settings_expose_optional_transcription_flags(self):
        self.assertTrue(hasattr(settings, 'enable_diarization'))
        self.assertTrue(hasattr(settings, 'ffmpeg_path'))
        self.assertIsNone(settings.ffmpeg_path)

    def test_build_timeline_events_uses_metadata_timestamps(self):
        doc = SimpleNamespace(
            page_content='The party reached the hidden gate at dawn.',
            metadata={
                'temporal_entities': ['dawn'],
                'location_entities': ['the hidden gate'],
                'start_time': 125.5,
            },
        )

        events = build_timeline_events_from_transcription_documents([doc], session_id='session-1')

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].timestamp, 125.5)
        self.assertEqual(events[0].session_id, 'session-1')
        self.assertTrue(events[0].title.lower().startswith('dawn'))


if __name__ == '__main__':
    unittest.main()
