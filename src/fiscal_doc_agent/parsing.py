"""Source Document -> per-page Markdown records, cached to disk."""

import json
from pathlib import Path

import pymupdf4llm

ROOT = Path(__file__).resolve().parents[2]
SOURCE_PDF = ROOT / "data" / "fy2024_analysis_of_revenue_and_expenditure.pdf"
CACHE_DIR = ROOT / ".cache"


def load_pages(pdf: Path = SOURCE_PDF, cache_dir: Path = CACHE_DIR) -> list[dict]:
    """Return [{"page": 1-based page number, "markdown": str}, ...] for every page."""
    cache = cache_dir / f"{pdf.stem}.pages.json"
    if cache.exists():
        return json.loads(cache.read_text())
    chunks = pymupdf4llm.to_markdown(str(pdf), page_chunks=True)
    pages = [{"page": c["metadata"]["page_number"], "markdown": c["text"]} for c in chunks]
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(pages, ensure_ascii=False))
    return pages
