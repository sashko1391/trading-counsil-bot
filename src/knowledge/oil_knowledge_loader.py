"""
OilKnowledgeLoader — Bulk-loads .md files from data/knowledge/ into the RAG engine.

CLI usage:
    python -m src.knowledge.oil_knowledge_loader
"""

from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path

from loguru import logger

from .rag_engine import OilRAGEngine


# Track ingested files to avoid duplicates
TRACKER_FILE = Path("data/knowledge/.ingested_tracker.json")


class OilKnowledgeLoader:
    """
    Loads all .md files from a knowledge directory into the RAG engine.
    Tracks ingested files by filename hash to skip duplicates.
    """

    def __init__(
        self,
        rag_engine: OilRAGEngine,
        knowledge_dir: Path = Path("data/knowledge"),
    ):
        self.rag_engine = rag_engine
        self.knowledge_dir = knowledge_dir
        self._tracker = self._load_tracker()

    # ------------------------------------------------------------------
    # Tracker persistence
    # ------------------------------------------------------------------

    def _load_tracker(self) -> dict:
        """Load the set of already-ingested file hashes."""
        tracker_path = self.knowledge_dir / ".ingested_tracker.json"
        if tracker_path.exists():
            try:
                return json.loads(tracker_path.read_text(encoding="utf-8"))
            except Exception:
                return {}
        return {}

    def _save_tracker(self) -> None:
        """Persist the tracker to disk."""
        tracker_path = self.knowledge_dir / ".ingested_tracker.json"
        tracker_path.parent.mkdir(parents=True, exist_ok=True)
        tracker_path.write_text(
            json.dumps(self._tracker, indent=2), encoding="utf-8"
        )

    @staticmethod
    def _file_hash(filepath: Path) -> str:
        """Compute a content-based hash for a file."""
        content = filepath.read_text(encoding="utf-8")
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    async def load_all(self) -> dict:
        """
        Load all .md files from knowledge_dir.

        Returns dict with stats: {loaded: int, skipped: int, failed: int, files: list}
        """
        md_files = sorted(self.knowledge_dir.glob("*.md"))

        if not md_files:
            logger.warning(f"No .md files found in {self.knowledge_dir}")
            return {"loaded": 0, "skipped": 0, "failed": 0, "files": []}

        loaded = 0
        skipped = 0
        failed = 0
        files_processed = []

        for filepath in md_files:
            file_hash = self._file_hash(filepath)

            # Skip already ingested files (same content hash)
            if filepath.name in self._tracker and self._tracker[filepath.name] == file_hash:
                logger.info(f"Skipping {filepath.name} (already ingested)")
                skipped += 1
                continue

            logger.info(f"Ingesting {filepath.name}...")
            try:
                count = await self.rag_engine.ingest_file(filepath)
                if count > 0:
                    self._tracker[filepath.name] = file_hash
                    loaded += 1
                    files_processed.append(filepath.name)
                    logger.info(f"  -> {count} chunks ingested")
                else:
                    failed += 1
                    logger.warning(f"  -> 0 chunks (possible error)")
            except Exception as exc:
                failed += 1
                logger.error(f"  -> Failed: {exc}")

        self._save_tracker()

        stats = {
            "loaded": loaded,
            "skipped": skipped,
            "failed": failed,
            "files": files_processed,
        }
        logger.info(f"Loading complete: {stats}")
        return stats


# ==============================================================================
# CLI entry point
# ==============================================================================

def main() -> None:
    """CLI entry point for bulk-loading knowledge files."""
    import sys

    logger.remove()
    logger.add(sys.stderr, format="<green>{time:HH:mm:ss}</green> | <level>{level: <7}</level> | {message}")

    # Try to load settings
    try:
        from config.settings import get_settings
        settings = get_settings()
        pinecone_key = settings.PINECONE_API_KEY
        openai_key = settings.OPENAI_API_KEY
        knowledge_dir = settings.KNOWLEDGE_PATH
    except Exception:
        import os
        pinecone_key = os.getenv("PINECONE_API_KEY", "")
        openai_key = os.getenv("OPENAI_API_KEY", "")
        knowledge_dir = Path("data/knowledge")

    engine = OilRAGEngine(
        pinecone_api_key=pinecone_key,
        openai_api_key=openai_key,
    )
    loader = OilKnowledgeLoader(
        rag_engine=engine,
        knowledge_dir=knowledge_dir,
    )

    stats = asyncio.run(loader.load_all())
    logger.info(f"Done: {stats['loaded']} loaded, {stats['skipped']} skipped, {stats['failed']} failed")


if __name__ == "__main__":
    main()
