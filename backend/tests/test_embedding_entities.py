"""Tests that embedding transcriptions hands back the chunks it saved, entities included."""

import unittest
from unittest import mock

from app.core.config import settings
from app.functions.embedding import embedding_model


class EmbedTranscriptionsReturnTests(unittest.TestCase):
    def setUp(self) -> None:
        patches = [
            mock.patch.object(embedding_model, 'SentenceTransformerEmbeddings', mock.Mock()),
            mock.patch.object(embedding_model, 'write_to_ChromaDB'),
            mock.patch.object(settings, 'entity_llm_fallback', False),
        ]
        self.write = patches[1].start()
        patches[0].start()
        patches[2].start()
        for patch in patches:
            self.addCleanup(patch.stop)

    def test_returns_the_saved_chunks_with_their_entities(self) -> None:
        saved = embedding_model.embedd_transcriptions(
            embedding_text=['We leave Neverwinter at dawn.', 'Pass me the snacks.'],
            speakers=['Ana', 'Ben'],
            timestamps=[1.0, 2.0],
            persist_directory='unused',
        )

        self.assertEqual(
            [doc.page_content for doc in saved],
            ['We leave Neverwinter at dawn.', 'Pass me the snacks.'],
        )
        self.assertIn('Neverwinter', saved[0].metadata['location_entities'])
        self.assertEqual(saved[1].metadata['location_entities'], '')

    def test_returns_exactly_the_documents_written_to_the_database(self) -> None:
        saved = embedding_model.embedd_transcriptions(
            embedding_text=['We leave Neverwinter at dawn.'],
            speakers=['Ana'],
            persist_directory='unused',
        )

        self.assertEqual(self.write.call_args.args[1], saved)


if __name__ == '__main__':
    unittest.main()
