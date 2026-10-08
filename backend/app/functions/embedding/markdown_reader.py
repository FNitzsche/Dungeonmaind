"""Utility for reading markdown file contents."""

import os


def read_markdown_file(md_path: str) -> str:
    """Read the raw text content of a markdown file.

    Args:
        md_path: Absolute path to the markdown file.

    Returns:
        The file content as a string.

    Raises:
        FileNotFoundError: If the file does not exist.
    """
    if not os.path.exists(md_path):
        raise FileNotFoundError(f'Markdown file not found: {md_path}')

    with open(md_path, encoding='utf-8') as f:
        content = f.read()

    return content
