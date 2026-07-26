import argparse
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from zipfile import ZipFile

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.functions.embedding.entity_extractor import entities_as_metadata, extract_entities_hybrid

DEFAULT_SAMPLES = [
    'Yesterday we met in Berlin at 8:30 PM.',
    'Next week go to Room 204 in Building A.',
    'On 12 June 2026 we left India.',
    'Tomorrow the party returns to the Tavern at 7 PM.',
]


def read_docx_paragraphs(path: Path) -> list[str]:
    namespace = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
    with ZipFile(path) as docx:
        document_xml = docx.read('word/document.xml')

    root = ET.fromstring(document_xml)
    paragraphs = []
    for paragraph in root.findall('.//w:p', namespace):
        text_parts = [node.text or '' for node in paragraph.findall('.//w:t', namespace)]
        text = ''.join(text_parts).strip()
        if text:
            paragraphs.append(text)
    return paragraphs


def extract_docx_level_paragraphs(path: Path) -> list[str]:
    paragraphs = read_docx_paragraphs(path)
    joined = '\n\n'.join(paragraphs)
    levels = []
    for level in range(1, 5):
        marker = f'LEVEL {level}:'
        start = joined.find(marker)
        if start < 0:
            continue
        expected_marker = 'Expected Temporal Entities:'
        expected_start = joined.find(expected_marker, start)
        starts = [
            joined.find(prefix, start, expected_start)
            for prefix in ('On ', 'Early ', 'Two ', 'Three ')
        ]
        valid_starts = [candidate for candidate in starts if candidate >= 0]
        paragraph_start = min(valid_starts) if valid_starts else -1
        if paragraph_start < 0 or expected_start < 0:
            continue
        level_text = joined[paragraph_start:expected_start].strip()
        if level_text:
            levels.append(level_text)
    return levels or paragraphs


def show_result(text: str, use_llm: bool = False) -> None:
    entities = extract_entities_hybrid(text, use_llm=use_llm)
    metadata = entities_as_metadata(text, use_llm=use_llm)

    print('=' * 72)
    print('Text:')
    print(text)
    print()
    print('Temporal entities:')
    print(entities.temporal_entities or 'None')
    print()
    print('Location entities:')
    print(entities.location_entities or 'None')
    print()
    print('Chroma metadata fields:')
    print(metadata)


def main() -> None:
    parser = argparse.ArgumentParser(
        description='Test Dungeonmaind temporal and location entity extraction.'
    )
    parser.add_argument(
        'text',
        nargs='*',
        help='Optional text or .docx path to test. If omitted, built-in sample texts are used.',
    )
    parser.add_argument(
        '--llm',
        action='store_true',
        help='Use local Ollama fallback in addition to rule-based extraction.',
    )
    args = parser.parse_args()

    if args.text:
        joined_input = ' '.join(args.text)
        input_path = Path(joined_input.strip('"'))
        if input_path.suffix.casefold() == '.docx' and input_path.exists():
            samples = extract_docx_level_paragraphs(input_path)
        else:
            samples = [joined_input]
    else:
        samples = DEFAULT_SAMPLES

    for sample in samples:
        show_result(sample, use_llm=args.llm)


if __name__ == '__main__':
    main()
