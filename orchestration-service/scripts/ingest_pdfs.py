"""Ingests a directory of PDFs into the shared RAG knowledge base

(rag_manager.KNOWLEDGE_BASE_SCOPE) — the intake tool for the emotional
agent's reference library (US-003) and any future shared reading material.

Usage (from orchestration-service/, with its venv active):
    python3 scripts/ingest_pdfs.py <directory> [--chunk-size N] [--overlap N]

Requires the `pdftotext` binary (poppler-utils: `brew install poppler`).
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import rag_manager  # noqa: E402


def extract_text(pdf_path: Path) -> str:
    result = subprocess.run(
        ['pdftotext', '-layout', str(pdf_path), '-'],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', help='Directory containing .pdf files to ingest')
    parser.add_argument('--chunk-size', type=int, default=1500)
    parser.add_argument('--overlap', type=int, default=200)
    args = parser.parse_args()

    pdf_dir = Path(args.directory)
    pdfs = sorted(pdf_dir.glob('*.pdf'))
    if not pdfs:
        print(f'No PDFs found in {pdf_dir}')
        return

    print(f'Found {len(pdfs)} PDF(s) to ingest into scope {rag_manager.KNOWLEDGE_BASE_SCOPE!r}\n', flush=True)

    for pdf_path in pdfs:
        title = pdf_path.stem
        print(f'--- {title} ---', flush=True)
        started = time.time()
        try:
            text = extract_text(pdf_path)
        except subprocess.CalledProcessError as exc:
            print(f'  FAILED to extract text: {exc}', flush=True)
            continue

        if not text.strip():
            print('  (no extractable text, skipping)', flush=True)
            continue

        result = rag_manager.ingest_text(
            profile_email=rag_manager.KNOWLEDGE_BASE_SCOPE,
            text=text,
            title=title,
            source_type='book',
            chunk_size=args.chunk_size,
            overlap=args.overlap,
        )
        elapsed = time.time() - started
        status = 'already ingested' if result['already_ingested'] else 'ingested'
        print(f'  {status}: {result["chunk_count"]} chunks in {elapsed:.1f}s', flush=True)

    print('\nDone.', flush=True)


if __name__ == '__main__':
    main()
