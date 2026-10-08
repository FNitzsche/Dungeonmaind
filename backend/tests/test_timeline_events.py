import unittest
from types import SimpleNamespace

from app.core.config import settings
from app.functions.llm.event_extractor import build_timeline_events_from_transcription_documents


class TimelineEventExtractorTests(unittest.TestCase):
    def test_settings_expose_optional_transcription_flags(self):
        self.assertTrue(hasattr(settings, 'enable_diarization'))
        self.assertTrue(hasattr(settings, 'ffmpeg_path'))
        self.assertIsNone(settings.ffmpeg_path)

    def test_build_timeline_events_uses_recording_timestamp_for_display_time(self):
        doc = SimpleNamespace(
            page_content='They departed at 06:45 AM from Velmora Crossing.',
            metadata={
                'temporal_entities': ['06:45 AM', 'dawn'],
                'location_entities': ['Velmora Crossing'],
                'start_time': 125.5,
            },
        )

        events = build_timeline_events_from_transcription_documents([doc], session_id='session-1')

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].timestamp, 125.5)
        self.assertEqual(events[0].display_time, '00:02:05')
        self.assertNotIn('06:45 AM', events[0].title)
        self.assertNotIn('Velmora Crossing', events[0].title)

    def test_build_timeline_events_falls_back_to_temporal_label_without_recording_time(self):
        doc = SimpleNamespace(
            page_content='The party reached the hidden gate at dawn.',
            metadata={
                'temporal_entities': ['dawn'],
                'location_entities': ['the hidden gate'],
            },
        )

        events = build_timeline_events_from_transcription_documents([doc], session_id='session-1')

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].timestamp, 0.0)
        self.assertEqual(events[0].display_time, 'Morning')
        self.assertNotIn('dawn', events[0].title.lower())


if __name__ == '__main__':
    unittest.main()
