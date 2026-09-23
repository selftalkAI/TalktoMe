from __future__ import annotations


def chunk_text(text: str, chunk_size: int = 800, overlap: int = 150) -> list[str]:
    """Splits text into overlapping, fixed-size character windows.

    Character-based rather than token-based — the simplest reliable unit that
    doesn't bind the pipeline to one tokenizer. This is a placeholder default;
    revisit (token-aware, semantic, or format-aware splitting) once real
    documents and their structure are known.
    """
    text = text.strip()
    if not text:
        return []
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError('overlap must be non-negative and smaller than chunk_size')

    chunks: list[str] = []
    step = chunk_size - overlap
    start = 0
    length = len(text)
    while start < length:
        end = start + chunk_size
        piece = text[start:end].strip()
        if piece:
            chunks.append(piece)
        if end >= length:
            break
        start += step
    return chunks
