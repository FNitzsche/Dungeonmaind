import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.functions.geographic_mapping.spatial_relation_extractor import extract_spatial_relations


class SpatialRelationTests(unittest.TestCase):
    def test_leader_examples(self):
        examples = [
            ("The village is north of Neverwinter.", "village", "Neverwinter", "north_of"),
            ("The ruined temple lies inside the forest.", "ruined temple", "forest", "inside"),
            ("The old bridge is near Waterdeep.", "old bridge", "Waterdeep", "near"),
            ("We travelled from Waterdeep to Neverwinter.", "Waterdeep", "Neverwinter", "travelled_to"),
        ]
        for text, source, target, relation in examples:
            with self.subTest(text=text):
                results = extract_spatial_relations(text)
                self.assertEqual(len(results), 1)
                result = results[0]
                self.assertEqual((result.source, result.target, result.relation.value), (source, target, relation))
                self.assertEqual(result.evidence, text)

    def test_all_relations(self):
        for phrase, relation in [
            ("is south of", "south_of"), ("is east of", "east_of"),
            ("is west of", "west_of"), ("is connected to", "connected_to"),
            ("contains", "contains"), ("is situated within", "inside"),
        ]:
            with self.subTest(phrase=phrase):
                self.assertEqual(extract_spatial_relations(f"Blackstone Keep {phrase} Ashen Forest.")[0].relation.value, relation)

    def test_no_invented_or_uncertain_edges(self):
        for text in ["Waterdeep and Neverwinter are cities.",
                     "The village is not north of Neverwinter.",
                     "The village might be north of Neverwinter.",
                     "Is the village north of Neverwinter?",
                     "We planned to travel from Waterdeep to Neverwinter.",
                     "We are near Waterdeep.", "Waterdeep is near Waterdeep.",
                     "The cave is near the forest and we rested.", ""]:
            with self.subTest(text=text):
                self.assertEqual(extract_spatial_relations(text), [])

    def test_multiple_sentences_and_american_spelling(self):
        results = extract_spatial_relations("The cave is near the forest. We traveled from Waterdeep to Neverwinter.")
        self.assertEqual(len(results), 2)
        self.assertEqual(results[1].relation.value, "travelled_to")
