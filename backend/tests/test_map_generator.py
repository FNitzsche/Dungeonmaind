import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pydantic import ValidationError
from app.base_models.map_models import MapData
from app.functions.geographic_mapping.map_generator import generate_map_from_documents, generate_map_from_embeddings


def document(text, start=0, end=1):
    return SimpleNamespace(page_content=text, metadata={"start_time": start, "end_time": end})


class MapGeneratorTests(unittest.TestCase):
    def test_nodes_edges_evidence_times_and_counts(self):
        documents = [document("The village is north of Neverwinter.", 10, 12),
                     document("We travelled from Neverwinter to Waterdeep.", 20, 24)]
        graph = generate_map_from_documents(documents)
        self.assertEqual(graph.source_segment_count, 2)
        self.assertEqual(len(graph.edges), 2)
        names = {node.id: node.name for node in graph.nodes}
        edge = graph.edges[0]
        self.assertEqual((names[edge.source], names[edge.target]), ("village", "Neverwinter"))
        self.assertEqual(edge.timestamp, 10)
        node = next(node for node in graph.nodes if node.name == "Neverwinter")
        self.assertEqual((node.mentions, node.first_seen, node.last_seen), (2, 10, 24))

    def test_repeat_generation_stable_and_order_independent(self):
        documents = [document("Waterdeep is near Neverwinter.", 4, 6),
                     document("We travelled from Neverwinter to Waterdeep.", 10, 12)]
        self.assertEqual(generate_map_from_documents(documents), generate_map_from_documents(reversed(documents)))

    def test_empty_text_and_bad_metadata(self):
        self.assertEqual(generate_map_from_documents([]), MapData())
        self.assertEqual(generate_map_from_documents([document(" ")]), MapData())
        graph = generate_map_from_documents([document("Waterdeep is near Neverwinter.", "invalid", float("nan"))])
        self.assertEqual(graph.edges[0].timestamp, 0)

    def test_isolated_location_and_repeated_mentions(self):
        graph = generate_map_from_documents([document("We arrived at Waterdeep. We rested at Waterdeep.")])
        node = next(node for node in graph.nodes if node.name == "Waterdeep")
        self.assertEqual(node.mentions, 2)
        self.assertEqual(graph.edges, [])

    def test_generic_locations_not_merged_across_segments(self):
        graph = generate_map_from_documents([document("The cave is near Waterdeep.", 0, 1),
                     document("The cave is near Neverwinter.", 2, 3)])
        self.assertEqual(len([node for node in graph.nodes if node.name == "cave"]), 2)

    def test_capitalization_and_article_normalization(self):
        graph = generate_map_from_documents([
            document("Waterdeep is near Neverwinter.", 0, 1),
            document("waterdeep is near neverwinter.", 2, 3),
        ])
        self.assertEqual(len(graph.nodes), 2)
        self.assertTrue(all(node.mentions == 2 for node in graph.nodes))

    def test_capitalized_generic_place_remains_local(self):
        graph = generate_map_from_documents([
            document("Cave is near Waterdeep.", 0, 1),
            document("Cave is near Neverwinter.", 2, 3),
        ])
        self.assertEqual(len([node for node in graph.nodes if node.name == "Cave"]), 2)

    def test_reads_existing_document_provider(self):
        fake = SimpleNamespace(get_all_transcription_documents=lambda: [document("Waterdeep is near Neverwinter.")])
        with patch.dict(sys.modules, {"app.functions.embedding.embedding_model": fake}):
            self.assertEqual(len(generate_map_from_embeddings().edges), 1)

    def test_compound_generic_named_places_share_identity(self):
        graph = generate_map_from_documents([
            document("Old Tower is inside Pine Forest.", 0, 3),
            document("We travelled from Pine Forest to Old Tower.", 4, 7),
            document("Hill Village is north of Old Tower.", 8, 11),
            document("We travelled from Old Tower to Hill Village.", 12, 15),
            document("Castle Gate is east of Hill Village.", 16, 19),
            document("We travelled from Hill Village to Castle Gate.", 20, 23),
        ])
        self.assertEqual({n.name for n in graph.nodes},
                         {"Old Tower", "Pine Forest", "Hill Village", "Castle Gate"})
        self.assertEqual(len(graph.nodes), 4)
        self.assertEqual(len(graph.edges), 6)
        self.assertEqual(next(n for n in graph.nodes if n.name == "Old Tower").mentions, 4)

    def test_incidental_generic_fragments_are_not_map_nodes(self):
        graph = generate_map_from_documents([
            document("Old Tower is inside Pine Forest.", 0, 3),
            document("We entered the tower and searched the abandoned rooms.", 4, 8),
            document("Hill Village is north of Old Tower.", 9, 12),
            document("We arrived at the village and waited beside the gate.", 13, 17),
        ])
        self.assertEqual({n.name for n in graph.nodes}, {"Old Tower", "Pine Forest", "Hill Village"})

    def test_sample_contract_and_invalid_graph(self):
        sample = json.loads((Path(__file__).parent / "data/map_sample.json").read_text())
        MapData.model_validate(sample)
        sample["edges"][0]["target"] = "missing"
        with self.assertRaises(ValidationError):
            MapData.model_validate(sample)
