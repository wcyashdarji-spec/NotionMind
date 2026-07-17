from __future__ import annotations

from typing import List

from src.config import logger


def chunk_text(
    text: str,
    chunk_size: int = 2000,
    chunk_overlap: int = 500,
) -> List[str]:
    """
    Split a document into overlapping text chunks aligned to paragraph boundaries.

    The algorithm walks paragraph blocks (split on ``\\n\\n``) and accumulates
    them until the running character count exceeds *chunk_size*.  When a
    boundary is reached the current window is flushed and the next window is
    seeded with up to *chunk_overlap* characters worth of trailing paragraphs
    from the previous window, preserving contextual continuity.

    Paragraphs that individually exceed *chunk_size* are split character-by-
    character with the same overlap stride applied between sub-chunks.

    Args:
        text: Raw markdown or plain text to split.
        chunk_size: Maximum character count per chunk. Defaults to ``2000``.
        chunk_overlap: Character budget carried forward as overlap between
            consecutive chunks. Defaults to ``500``.

    Returns:
        Ordered list of non-empty text chunk strings.

    Raises:
        ValueError: If *chunk_overlap* is greater than or equal to *chunk_size*.
    """
    if chunk_overlap >= chunk_size:
        raise ValueError(
            f"chunk_overlap ({chunk_overlap}) must be smaller than chunk_size ({chunk_size})."
        )

    if not text or not text.strip():
        return []

    try:
        paragraphs = text.split("\n\n")
        chunks: List[str] = []
        current_chunk: List[str] = []
        current_size: int = 0

        for paragraph in paragraphs:
            if not paragraph.strip():
                continue

            p_len = len(paragraph)

            if p_len > chunk_size:
                if current_chunk:
                    chunks.append("\n\n".join(current_chunk))
                    current_chunk = []
                    current_size = 0

                start = 0
                while start < p_len:
                    chunks.append(paragraph[start : start + chunk_size])
                    start += chunk_size - chunk_overlap

            else:
                if current_size + p_len > chunk_size and current_chunk:
                    chunks.append("\n\n".join(current_chunk))

                    overlap_paragraphs: List[str] = []
                    overlap_budget = 0
                    for prev in reversed(current_chunk):
                        if overlap_budget + len(prev) < chunk_overlap:
                            overlap_paragraphs.insert(0, prev)
                            overlap_budget += len(prev)
                        else:
                            break

                    current_chunk = overlap_paragraphs
                    current_size = sum(len(p) for p in current_chunk)

                current_chunk.append(paragraph)
                current_size += p_len + 2

        if current_chunk:
            chunks.append("\n\n".join(current_chunk))

        logger.debug(f"chunk_text produced {len(chunks)} chunks from {len(text)} characters.")
        return chunks

    except Exception as exc:
        logger.error(f"chunk_text failed: {exc}")
        raise
