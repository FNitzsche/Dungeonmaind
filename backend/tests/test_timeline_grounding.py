import importlib.util
import json
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import Mock, patch

import numpy  # Load once outside patch.dict: native modules cannot be reimported.

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.functions.timeline import timeline_ai as ai
from app.base_models.timeline_models import TimelineCategory, TimelineSourceSegment


def load_generator():
    # Isolate heavyweight model/database dependencies; exercise the real generator
    # and models without downloading embeddings or starting Chroma/Ollama.
    stubs = {}
    for name, attributes in {
        'sentence_transformers': {'SentenceTransformer': Mock()},
        'langchain_core.documents': {'Document': Mock()},
        'app.functions.embedding.embedding_model': {'get_all_transcription_documents': Mock()},
        'app.functions.timeline.event_detector': {'semantic_event_decision': Mock()},
    }.items():
        module = types.ModuleType(name)
        module.__dict__.update(attributes)
        stubs[name] = module
    spec = importlib.util.spec_from_file_location(
        '_timeline_generator_under_test',
        BACKEND_DIR / 'app/functions/timeline/timeline_generator.py',
    )
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, stubs):
        spec.loader.exec_module(module)
    return module


class TimelineGroundingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.generator = load_generator()

    def setUp(self):
        ai.analyze_timeline_event.cache_clear()
        self.addCleanup(ai.analyze_timeline_event.cache_clear)

    def analyze(self, text, **overrides):
        data = dict(keep=True, occurred=True, importance=0.9, category='item',
                    evidence=text, title='The party obtains the legendary Sword of Doom',
                    locations=[], temporal_entities=[])
        data.update(overrides)
        response = Mock()
        response.json.return_value = {'message': {'content': json.dumps(data)}}
        ai.analyze_timeline_event.cache_clear()
        with patch.object(ai, 'TIMELINE_AI_ENABLED', True), patch.object(
            ai.requests, 'post', return_value=response
        ):
            return ai.analyze_timeline_event(text)

    def group(self, text):
        return [TimelineSourceSegment(text=text, speaker='DM', start_time=0, end_time=10)]

    def test_obtained_item_uses_source_not_invented_title(self):
        text = 'Aria received the silver key from the guard.'
        result = self.analyze(text)
        self.assertTrue(result.keep)
        self.assertEqual(result.title, text)
        self.assertEqual(result.evidence, text)

    def test_item_mention_is_rejected_even_when_ai_confirms_occurrence(self):
        for text in ['The guard mentioned the silver key.', 'The silver key lies on the table.']:
            with self.subTest(text=text):
                self.assertFalse(self.analyze(text, keep=True, occurred=True, category="item").keep)

    def test_proposal_and_negation_are_not_completed_actions(self):
        for text in ['I am going to take the silver key.', 'Aria would take the silver key.',
                     'Aria did not receive the silver key.', 'If Aria received the key, we could enter.']:
            with self.subTest(text=text):
                self.assertFalse(self.analyze(text, keep=True, occurred=True, category="item").keep)
                self.assertIsNone(self.generator._build_title(TimelineCategory.item, text, []))
        self.assertTrue(self.analyze('Aria took the silver key.').keep)

    def test_great_weapon_master_is_not_item_acquisition(self):
        for text in ['I am going to take all three attacks at Great Weapon Master at him',
                     'I take all three attacks at Great Weapon Master at him.']:
            with self.subTest(text=text):
                self.assertFalse(self.analyze(text, keep=True, occurred=True, category="item").keep)
                self.assertIsNone(self.generator._build_title(TimelineCategory.item, text, []))

    def test_actual_item_actions_pass_shared_ai_and_offline_validation(self):
        for text in [
            'Aria received the silver key from the guard.',
            'The guard gave Aria the silver key.',
            'Aria lost the silver key.',
            'Aria could not open the chest, but the guard gave her the key.',
        ]:
            with self.subTest(text=text):
                result = self.analyze(text, keep=True, occurred=True, category='item')
                self.assertTrue(result.keep)
                self.assertEqual(result.title, text)
                self.assertEqual(self.generator._build_title(TimelineCategory.item, text, []), text)

    def test_rules_actions_are_not_item_events_despite_ai_confirmation(self):
        for text in [
            'I take the attack action.',
            'I use three dice for the damage roll.',
            'I use my proficiency bonus.',
            'I use advantage on the ability check.',
            'I use a d20.',
        ]:
            with self.subTest(text=text):
                self.assertFalse(self.analyze(text, keep=True, occurred=True, category='item').keep)
                self.assertIsNone(self.generator._build_title(TimelineCategory.item, text, []))

    def test_ai_item_validation_checks_selected_evidence_not_other_sentences(self):
        mention = 'The guard mentioned the silver key.'
        text = mention + ' Aria received a potion.'
        self.assertFalse(self.analyze(text, evidence=mention, occurred=True, category='item').keep)

    def test_missing_invalid_or_invented_evidence_rejects_event(self):
        text = 'Aria received the silver key.'
        for evidence in [None, '', [], 42, 'Aria received the golden crown.']:
            with self.subTest(evidence=evidence):
                self.assertFalse(self.analyze(text, evidence=evidence).keep)

    def test_substring_cannot_strip_conditions_or_negation(self):
        self.assertFalse(self.analyze(
            'If Aria took the key, the door would open.', evidence='Aria took the key'
        ).keep)
        self.assertFalse(self.analyze(
            'Nobody said Aria received the key.', evidence='Aria received the key.'
        ).keep)

    def test_grounding_restores_source_casing_and_preserves_entities(self):
        text = 'At dawn Aria received the key in Waterdeep.'
        result = self.analyze(text, evidence=text.lower(),
                              locations=['Waterdeep', 'Neverwinter'],
                              temporal_entities=['At dawn', 'tomorrow'])
        self.assertTrue(result.keep)
        self.assertEqual(result.title, text)
        self.assertEqual(result.locations, ('Waterdeep',))
        self.assertEqual(result.temporal_entities, ('At dawn',))

    def test_occurred_and_keep_must_be_boolean_true(self):
        for overrides in [dict(occurred=False), dict(occurred='true'), dict(keep='false')]:
            with self.subTest(overrides=overrides):
                self.assertFalse(self.analyze('Aria received the silver key.', **overrides).keep)

    def test_fallback_titles_quote_evidence_for_all_categories(self):
        for category, text in [(TimelineCategory.item, 'Aria lost the silver key.'),
                               (TimelineCategory.combat, 'The battle ended at dawn.'),
                               (TimelineCategory.quest, 'The party completed the quest.'),
                               (TimelineCategory.travel, 'The party arrived in Waterdeep.')]:
            with self.subTest(category=category):
                self.assertEqual(self.generator._build_title(category, text, ['Invented']), text)

    def test_overlong_evidence_keeps_event_and_full_evidence(self):
        text = ('After walking along the winding road through the forest for several days '
                'and crossing the old stone bridge, we finally arrived in Waterdeep.')
        result = self.analyze(text, category='travel')
        self.assertTrue(result.keep)
        self.assertEqual(result.evidence, text)
        self.assertLessEqual(len(result.title), 120)
        self.assertTrue(result.title.startswith('Excerpt: “'))
        self.assertTrue(result.title.endswith('…”'))
        self.assertIn(result.title[len('Excerpt: “'):-2], text)
        self.assertEqual(self.generator._build_title(TimelineCategory.travel, text, []),
                         result.title)
        event = self.generator._create_event_from_group(self.group(text), ai_analysis=result)
        self.assertEqual(event.title, result.title)

    def test_long_unoccurred_event_is_still_rejected(self):
        text = 'Aria received the key ' + 'from the guard ' * 10 + 'only in her imagination.'
        self.assertFalse(self.analyze(text, occurred=False).keep)

    def test_completed_ai_events_allow_modals_and_negation(self):
        for category, text in [
            ('combat', 'The goblin could not escape, and the party killed him.'),
            ('travel', "We didn't stop and eventually arrived in Waterdeep."),
            ('combat', 'The king would not surrender, so the party attacked.'),
            ('item', 'Aria could not open the chest, but the guard gave her the key.'),
        ]:
            with self.subTest(text=text):
                result = self.analyze(text, category=category)
                self.assertTrue(result.keep)
                self.assertEqual(result.title, text)
                self.assertEqual(result.evidence, text)

    def test_non_item_offline_filter_does_not_construct_titles(self):
        for category, text in [
            (TimelineCategory.combat, 'The goblin could not escape, and the party killed him.'),
            (TimelineCategory.travel, "We didn't stop and eventually arrived in Waterdeep."),
            (TimelineCategory.combat, 'The king would not surrender, so the party attacked.'),
            (TimelineCategory.discovery, 'We discovered the hidden underground passage.'),
        ]:
            with self.subTest(category=category), \
                 patch.object(self.generator, '_detect_category', return_value=category), \
                 patch.object(self.generator, '_build_title', return_value=None) as title, \
                 patch.object(self.generator, 'semantic_event_decision', return_value=types.SimpleNamespace(
                     keep=True, non_event_score=0.1, margin=0.5)):
                self.assertTrue(self.generator._is_meaningful_group(self.group(text)))
                title.assert_not_called()

    def test_fallback_selects_event_sentence_after_filler(self):
        for category, sentence in [
            (TimelineCategory.travel, 'We finally arrived in Waterdeep.'),
            (TimelineCategory.combat, 'The party killed the goblin.'),
            (TimelineCategory.discovery, 'We discovered the hidden passage.'),
        ]:
            with self.subTest(category=category):
                text = 'Okay everyone, here we go. ' + sentence
                self.assertEqual(self.generator._build_title(category, text, []), sentence)

    def test_fallback_reuses_semantic_ranking_without_keyword_matches(self):
        text = 'Okay everyone, here we go. We made it to Waterdeep.'
        with patch.object(self.generator, '_semantic_category_scores', side_effect=[
            {TimelineCategory.travel: 0.1}, {TimelineCategory.travel: 0.8},
        ]):
            self.assertEqual(self.generator._build_title(TimelineCategory.travel, text, []),
                             'We made it to Waterdeep.')

    def test_offline_item_guard_does_not_discard_unrelated_negation(self):
        text = 'Aria could not open the chest, but the guard gave her the key.'
        self.assertEqual(self.generator._build_title(TimelineCategory.item, text, []), text)

    def test_fallback_skips_intent_and_uses_actual_action(self):
        text = 'Aria wanted to take the key. The guard gave her the key.'
        self.assertEqual(self.generator._build_title(TimelineCategory.item, text, []),
                         'The guard gave her the key.')

    def test_generator_rejects_unsubstantiated_ai_event(self):
        text = 'The guard mentioned the silver key.'
        analysis = self.analyze(text, occurred=False)
        self.assertIsNone(self.generator._create_event_from_group(
            self.group(text), ai_analysis=analysis))

    def test_offline_generator_requires_item_action_evidence(self):
        with patch.object(self.generator, '_detect_category', return_value=TimelineCategory.item), \
             patch.object(self.generator, '_extract_event_entities', return_value=([], [])), \
             patch.object(self.generator, 'semantic_event_decision', return_value=types.SimpleNamespace(
                 keep=True, non_event_score=0.1, margin=0.5)):
            for text in ['The guard mentioned the silver key.',
                         'I am going to take all three attacks at Great Weapon Master at him']:
                self.assertFalse(self.generator._is_meaningful_group(self.group(text)))
                self.assertIsNone(self.generator._create_event_from_group(self.group(text)))
            text = 'The guard gave Aria the silver key.'
            self.assertTrue(self.generator._is_meaningful_group(self.group(text)))
            self.assertEqual(self.generator._create_event_from_group(self.group(text)).title, text)

    def test_failed_merge_preserves_grounded_original_events(self):
        first, second = Mock(), Mock()
        with patch.object(self.generator, '_events_are_similar', return_value=True), \
             patch.object(self.generator, '_merge_two_events', return_value=None):
            self.assertEqual(self.generator._merge_similar_events([first, second]), [first, second])

    def test_generation_omits_rejected_events_before_sorting(self):
        generator = self.generator
        text = 'Aria received the silver key.'
        group = self.group(text)
        accepted = self.analyze(text)
        rejected = self.analyze('The guard mentioned the silver key.', occurred=False)
        with patch.object(generator, 'get_all_transcription_documents', return_value=[]), \
             patch.object(generator, '_expand_documents_into_segments', return_value=group), \
             patch.object(generator, '_group_segments', return_value=[group, group]), \
             patch.object(generator, '_is_meaningful_group', return_value=True), \
             patch.object(generator, 'analyze_timeline_events', return_value=[accepted, rejected]) as batch:
            events, count = generator.generate_timeline_from_embeddings()
        batch.assert_called_once()
        self.assertEqual(count, 1)
        self.assertEqual([event.title for event in events], [text])


class TimelineBatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.generator = load_generator()

    def setUp(self):
        enabled = patch.object(ai, 'TIMELINE_AI_ENABLED', True)
        enabled.start()
        self.addCleanup(enabled.stop)

    @staticmethod
    def row(index, text, **overrides):
        result = dict(id=index, keep=True, occurred=True, importance=0.9,
                      category='travel', evidence=text, locations=['Waterdeep'],
                      temporal_entities=['At dawn'])
        result.update(overrides)
        return result

    @staticmethod
    def response(rows):
        response = Mock()
        response.json.return_value = {'message': {'content': json.dumps({'results': rows})}}
        return response

    def respond(self, url, *, json, timeout):
        import json as json_module
        items = json_module.loads(json['messages'][1]['content'])
        return self.response([self.row(item['id'], item['transcript']) for item in reversed(items)])

    def test_full_pipeline_batches_once_and_merges_without_reanalysis(self):
        generator = self.generator
        groups = [[TimelineSourceSegment(
            text=f'At dawn the party arrived in Waterdeep via gate {i}.',
            speaker='DM', start_time=i * 10, end_time=i * 10 + 10,
        )] for i in range(17)]
        segments = [group[0] for group in groups]
        with patch.object(generator, 'get_all_transcription_documents', return_value=[]), \
             patch.object(generator, '_expand_documents_into_segments', return_value=segments), \
             patch.object(generator, '_group_segments', return_value=groups), \
             patch.object(generator, 'semantic_event_decision', return_value=types.SimpleNamespace(
                 keep=True, non_event_score=0.1, margin=0.5)), \
             patch.object(generator, '_detect_category', return_value=TimelineCategory.travel), \
             patch.object(ai, 'analyze_timeline_event', side_effect=AssertionError('single analysis')), \
             patch.object(ai.requests, 'post', side_effect=self.respond) as post:
            events, count = generator.generate_timeline_from_embeddings()
        self.assertEqual(post.call_count, 3)
        self.assertEqual(count, 17)
        self.assertEqual(len(events), 2)
        self.assertEqual(sum(len(e.source_segments) for e in events), 17)
        self.assertEqual(events[0].title, segments[0].text)
        self.assertEqual(events[0].locations, ['Waterdeep'])
        self.assertEqual(events[0].temporal_entities, ['At dawn'])
        self.assertTrue(all(e.end_time - e.start_time <= 120 for e in events))

    def test_local_filter_never_calls_ollama(self):
        group = [TimelineSourceSegment(text='The party arrived in Waterdeep.', end_time=10)]
        with patch.object(self.generator, 'semantic_event_decision', return_value=types.SimpleNamespace(
                keep=True, non_event_score=0.1, margin=0.5)), \
             patch.object(self.generator, '_detect_category', return_value=TimelineCategory.travel), \
             patch.object(ai.requests, 'post') as post:
            self.assertTrue(self.generator._is_meaningful_group(group))
        post.assert_not_called()

    def test_batch_grounding_uses_own_source_and_item_guard(self):
        texts = ['At dawn the party arrived in Waterdeep.',
                 'The guard mentioned the silver key.',
                 'If Aria took the key, the door would open.',
                 'The party rested at night.']
        rows = [self.row(0, texts[0].lower(), locations=['Waterdeep', 'Neverwinter']),
                self.row(1, texts[1], category='item'),
                self.row(2, 'Aria took the key', category='item'),
                self.row(3, texts[0])]
        with patch.object(ai.requests, 'post', return_value=self.response(rows)):
            results = ai.analyze_timeline_events([(text, '') for text in texts])
        self.assertEqual([r.keep for r in results], [True, False, False, False])
        self.assertEqual(results[0].title, texts[0])
        self.assertEqual(results[0].locations, ('Waterdeep',))
        self.assertEqual(results[3].locations, ())
        self.assertEqual(results[3].temporal_entities, ())

    def test_missing_duplicate_and_unknown_ids_do_not_shift_results(self):
        texts = ['The party arrived in Waterdeep.'] * 4
        rows = [self.row(2, texts[2]), self.row(0, texts[0]), self.row(0, texts[0]),
                self.row(99, texts[0]), self.row(True, texts[0]), 'invalid']
        with patch.object(ai.requests, 'post', return_value=self.response(rows)):
            results = ai.analyze_timeline_events([(text, '') for text in texts])
        self.assertEqual([r is None for r in results], [True, True, False, True])

    def test_outage_stops_remaining_batches_and_local_creation_still_works(self):
        text = 'The party arrived in Waterdeep.'
        with patch.object(ai.requests, 'post', side_effect=ai.requests.Timeout()) as post:
            results = ai.analyze_timeline_events([(text, '')] * 25)
        self.assertEqual(results, [None] * 25)
        post.assert_called_once()
        with patch.object(self.generator, '_detect_category', return_value=TimelineCategory.travel), \
             patch.object(self.generator, '_extract_event_entities', return_value=([], [])), \
             patch.object(ai.requests, 'post') as post:
            event = self.generator._create_event_from_group([
                TimelineSourceSegment(text=text, end_time=10)], ai_analysis=results[0])
        self.assertEqual(event.title, text)
        post.assert_not_called()

    def test_disabled_and_empty_inputs_make_no_requests(self):
        with patch.object(ai.requests, 'post') as post:
            self.assertEqual(ai.analyze_timeline_events([]), [])
            with patch.object(ai, 'TIMELINE_AI_ENABLED', False):
                self.assertEqual(ai.analyze_timeline_events([('some text', '')]), [None])
        post.assert_not_called()

    def test_malformed_batch_falls_back_without_single_candidate_retries(self):
        response = Mock()
        response.json.return_value = {'message': {'content': 'not json'}}
        with patch.object(ai.requests, 'post', side_effect=[response, self.response([
                self.row(8, 'The party arrived in Waterdeep.')])]) as post:
            results = ai.analyze_timeline_events([('The party arrived in Waterdeep.', '')] * 9)
        self.assertEqual(post.call_count, 2)
        self.assertEqual(results[:8], [None] * 8)
        self.assertTrue(results[8].keep)

    def test_batches_bound_text_size_without_truncating_sources(self):
        texts = ['A' * 6000, 'B' * 6000, 'C' * 12001]
        with patch.object(ai.requests, 'post', side_effect=self.respond) as post:
            results = ai.analyze_timeline_events([(text, '') for text in texts])
        self.assertEqual(post.call_count, 2)
        self.assertEqual(results[0].evidence, texts[0])
        self.assertEqual(results[1].evidence, texts[1])
        self.assertIsNone(results[2])

    def test_grouping_allows_more_than_six_segments_and_checks_incoming_end(self):
        segments = [TimelineSourceSegment(text='We continued along the road.',
                    start_time=i * 10, end_time=i * 10 + 10) for i in range(13)]
        with patch.object(self.generator, '_detect_segment_category', return_value=TimelineCategory.travel), \
             patch.object(self.generator, '_contains_boundary_phrase', return_value=False):
            groups = self.generator._group_segments(segments)
        self.assertEqual([len(group) for group in groups], [12, 1])


if __name__ == '__main__':
    unittest.main()
