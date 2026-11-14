"""Tests for LLM-based event extraction with the Ollama call replaced by a fake."""

import json
import unittest
from unittest import mock
from urllib.error import URLError

from app.domain.models import TimelineEventType
from app.functions.embedding.entity_extractor import ExtractedEntities
from app.functions.llm import event_extractor


class _FakeResponse:
    def __init__(self, payload: dict | str) -> None:
        body = payload if isinstance(payload, str) else json.dumps(payload)
        self._body = body.encode('utf-8')

    def read(self) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *args) -> bool:
        return False


def _chat_reply(content: str) -> _FakeResponse:
    return _FakeResponse({'message': {'role': 'assistant', 'content': content}})


EVENTS_JSON = json.dumps(
    [
        {
            'title': 'Explorers Depart',
            'description': 'The party leaves Neverwinter at dawn.',
            'event_type': 'travel',
            'characters': ['Sildar'],
        },
        {
            'title': 'Ambush Sprung',
            'description': 'Goblins attack on the Triboar Trail.',
            'event_type': 'COMBAT',
        },
    ]
)


class ExtractEventsFromTextTests(unittest.TestCase):
    def setUp(self) -> None:
        entities = ExtractedEntities(
            temporal_entities=['dawn'], location_entities=['Neverwinter', 'Triboar Trail']
        )
        patch = mock.patch.object(event_extractor, 'extract_entities_hybrid', return_value=entities)
        patch.start()
        self.addCleanup(patch.stop)

    def _extract(self, reply, **kwargs):
        with mock.patch.object(event_extractor, 'urlopen', return_value=reply) as urlopen:
            events = event_extractor.extract_events_from_text(
                'We leave Neverwinter at dawn.', session_id='sess-1', **kwargs
            )
        return events, urlopen

    def test_events_are_built_from_the_llm_reply(self) -> None:
        events, _ = self._extract(
            _chat_reply(EVENTS_JSON), chunk_start_time=75.0, speaker_name='Ana'
        )

        self.assertEqual([event.title for event in events], ['Explorers Depart', 'Ambush Sprung'])
        self.assertEqual(
            [event.event_type for event in events],
            [TimelineEventType.travel, TimelineEventType.combat],
        )
        first = events[0]
        self.assertEqual(first.session_id, 'sess-1')
        self.assertEqual(first.timestamp, 75.0)
        self.assertEqual(first.display_time, '00:01:15')
        self.assertEqual(first.speaker_name, 'Ana')
        self.assertEqual(first.characters, ['Ana', 'Sildar'])
        self.assertEqual(first.temporal_entities, ['dawn'])
        self.assertEqual(first.location_entities, ['Neverwinter', 'Triboar Trail'])
        self.assertEqual(first.id, '')

    def test_request_goes_to_the_configured_ollama_chat_endpoint(self) -> None:
        _, urlopen = self._extract(_chat_reply(EVENTS_JSON))

        request = urlopen.call_args.args[0]
        payload = json.loads(request.data.decode('utf-8'))
        self.assertTrue(request.full_url.endswith('/api/chat'))
        self.assertEqual(request.get_method(), 'POST')
        self.assertFalse(payload['stream'])
        self.assertEqual(payload['messages'][0]['role'], 'system')
        self.assertIn('We leave Neverwinter at dawn.', payload['messages'][1]['content'])

    def test_json_wrapped_in_prose_is_still_parsed(self) -> None:
        events, _ = self._extract(_chat_reply(f'Sure! Here are the events:\n{EVENTS_JSON}\nDone.'))

        self.assertEqual(len(events), 2)

    def test_events_object_wrapper_is_accepted(self) -> None:
        events, _ = self._extract(_chat_reply(json.dumps({'events': json.loads(EVENTS_JSON)})))

        self.assertEqual(len(events), 2)

    def test_unknown_event_type_becomes_other(self) -> None:
        reply = json.dumps([{'title': 'Odd Thing', 'description': 'Hm.', 'event_type': 'party'}])

        events, _ = self._extract(_chat_reply(reply))

        self.assertEqual(events[0].event_type, TimelineEventType.other)

    def test_entries_without_title_or_description_are_skipped(self) -> None:
        reply = json.dumps(
            [
                {'title': '', 'description': 'No title.'},
                {'title': 'No description'},
                'not-an-object',
                {'title': 'Kept', 'description': 'Complete entry.'},
            ]
        )

        events, _ = self._extract(_chat_reply(reply))

        self.assertEqual([event.title for event in events], ['Kept'])

    def test_unparseable_reply_gives_no_events(self) -> None:
        for content in ('', 'I could not find any events.', '[{"title": '):
            with self.subTest(content=content):
                events, _ = self._extract(_chat_reply(content))
                self.assertEqual(events, [])

    def test_unreachable_ollama_gives_no_events(self) -> None:
        with mock.patch.object(event_extractor, 'urlopen', side_effect=URLError('refused')):
            events = event_extractor.extract_events_from_text('We leave.', session_id='sess-1')

        self.assertEqual(events, [])

    def test_non_json_http_body_gives_no_events(self) -> None:
        events, _ = self._extract(_FakeResponse('<html>502 Bad Gateway</html>'))

        self.assertEqual(events, [])

    def test_blank_text_does_not_call_the_llm(self) -> None:
        with mock.patch.object(event_extractor, 'urlopen') as urlopen:
            events = event_extractor.extract_events_from_text('   ', session_id='sess-1')

        self.assertEqual(events, [])
        urlopen.assert_not_called()


class ExtractEventsFromTranscriptionsTests(unittest.TestCase):
    def test_each_non_blank_text_is_extracted_with_its_speaker_and_time(self) -> None:
        with mock.patch.object(
            event_extractor, 'extract_events_from_text', return_value=[]
        ) as extract:
            event_extractor.extract_events_from_transcriptions(
                texts=['First.', '  ', 'Third.'],
                speakers=['Ana', 'Ben', 'DM'],
                timestamps=[1.0, 2.0, 3.0],
                session_id='sess-1',
            )

        calls = [call.kwargs for call in extract.call_args_list]
        self.assertEqual([call['text'] for call in calls], ['First.', 'Third.'])
        self.assertEqual([call['speaker_name'] for call in calls], ['Ana', 'DM'])
        self.assertEqual([call['chunk_start_time'] for call in calls], [1.0, 3.0])
        self.assertEqual({call['session_id'] for call in calls}, {'sess-1'})

    def test_missing_speakers_and_times_fall_back_to_defaults(self) -> None:
        with mock.patch.object(
            event_extractor, 'extract_events_from_text', return_value=[]
        ) as extract:
            event_extractor.extract_events_from_transcriptions(texts=['Only text.'])

        kwargs = extract.call_args.kwargs
        self.assertIsNone(kwargs['speaker_name'])
        self.assertEqual(kwargs['chunk_start_time'], 0.0)
        self.assertEqual(kwargs['session_id'], 'default')


if __name__ == '__main__':
    unittest.main()
