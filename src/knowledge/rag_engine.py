"""
OilRAGEngine — Retrieval-Augmented Generation for oil trading knowledge.

Uses Pinecone (REST API via httpx) for vector storage and
OpenAI text-embedding-3-small for embeddings.
"""

from __future__ import annotations

import hashlib
import math
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import httpx
from loguru import logger

# Try importing pinecone SDK (optional)
try:
    from pinecone import Pinecone as PineconeSDK

    HAS_PINECONE_SDK = True
except ImportError:
    HAS_PINECONE_SDK = False


# ============================================================
# Constants
# ============================================================

INDEX_NAME = "oil-knowledge"
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSION = 1536
MAX_CHUNK_TOKENS = 500
OPENAI_EMBED_URL = "https://api.openai.com/v1/embeddings"


class OilRAGEngine:
    """
    RAG engine backed by Pinecone vector DB and OpenAI embeddings.

    Works in two modes:
    1. pinecone-client SDK (if installed)
    2. Pinecone REST API via httpx (fallback)

    If API keys are missing, methods degrade gracefully:
    - query() returns []
    - ingest() returns ""
    - ingest_file() returns 0
    """

    def __init__(
        self,
        pinecone_api_key: str = "",
        openai_api_key: str = "",
        index_name: str = INDEX_NAME,
    ):
        self.pinecone_api_key = pinecone_api_key
        self.openai_api_key = openai_api_key
        self.index_name = index_name
        self._index = None
        self._pinecone_host: Optional[str] = None

        if not self.pinecone_api_key:
            logger.warning("PINECONE_API_KEY not set — RAG engine disabled (queries return empty)")
        if not self.openai_api_key:
            logger.warning("OPENAI_API_KEY not set — RAG engine disabled (no embeddings)")

        # If SDK available, initialise Pinecone client
        if self._keys_present and HAS_PINECONE_SDK:
            try:
                pc = PineconeSDK(api_key=self.pinecone_api_key)
                # Create index if it doesn't exist
                existing = [idx.name for idx in pc.list_indexes()]
                if self.index_name not in existing:
                    from pinecone import ServerlessSpec

                    pc.create_index(
                        name=self.index_name,
                        dimension=EMBEDDING_DIMENSION,
                        metric="cosine",
                        spec=ServerlessSpec(cloud="aws", region="us-east-1"),
                    )
                    logger.info(f"Created Pinecone index '{self.index_name}'")
                self._index = pc.Index(self.index_name)
                logger.info(f"Pinecone SDK index '{self.index_name}' ready")
            except Exception as exc:
                logger.warning(f"Pinecone SDK init failed, falling back to REST: {exc}")
                self._index = None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @property
    def _keys_present(self) -> bool:
        return bool(self.pinecone_api_key) and bool(self.openai_api_key)

    async def _get_embedding(self, text: str) -> list[float]:
        """Get embedding vector from OpenAI API."""
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                OPENAI_EMBED_URL,
                headers={
                    "Authorization": f"Bearer {self.openai_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": EMBEDDING_MODEL,
                    "input": text,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return data["data"][0]["embedding"]

    async def _resolve_pinecone_host(self) -> str:
        """Resolve the Pinecone index host via REST API."""
        if self._pinecone_host:
            return self._pinecone_host

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                "https://api.pinecone.io/indexes",
                headers={"Api-Key": self.pinecone_api_key},
            )
            resp.raise_for_status()
            indexes = resp.json().get("indexes", [])

            for idx in indexes:
                if idx["name"] == self.index_name:
                    self._pinecone_host = idx["host"]
                    return self._pinecone_host

            # Index doesn't exist — create it
            resp = await client.post(
                "https://api.pinecone.io/indexes",
                headers={
                    "Api-Key": self.pinecone_api_key,
                    "Content-Type": "application/json",
                },
                json={
                    "name": self.index_name,
                    "dimension": EMBEDDING_DIMENSION,
                    "metric": "cosine",
                    "spec": {
                        "serverless": {
                            "cloud": "aws",
                            "region": "us-east-1",
                        }
                    },
                },
            )
            resp.raise_for_status()
            self._pinecone_host = resp.json()["host"]
            logger.info(f"Created Pinecone index '{self.index_name}' via REST")
            return self._pinecone_host

    # ------------------------------------------------------------------
    # Confidence decay
    # ------------------------------------------------------------------

    @staticmethod
    def apply_confidence_decay(
        score: float,
        ingested_at: str | None,
        chunk_type: str = "fact",
        news_lambda: float = 0.05,
        fact_lambda: float = 0.005,
        now: datetime | None = None,
    ) -> float:
        """Apply time-based decay: adjusted = score × e^(−λ × hours)."""
        if not ingested_at:
            return score
        try:
            ts = datetime.fromisoformat(ingested_at.replace("Z", "+00:00"))
            now = now or datetime.now(tz=timezone.utc)
            hours = max((now - ts).total_seconds() / 3600, 0)
        except (ValueError, TypeError):
            return score

        lam = news_lambda if chunk_type == "news" else fact_lambda
        return score * math.exp(-lam * hours)

    # ------------------------------------------------------------------
    # Chunk splitting
    # ------------------------------------------------------------------

    @staticmethod
    def split_into_chunks(text: str, max_tokens: int = MAX_CHUNK_TOKENS) -> list[str]:
        """
        Split text into chunks:
        1. First split by '---' separator
        2. Then split large sections by paragraphs
        3. Merge small paragraphs, split large ones to stay under max_tokens
        """
        # Approximate: 1 token ~ 4 chars
        max_chars = max_tokens * 4

        # Step 1: split by '---'
        sections = re.split(r"\n-{3,}\n", text)

        chunks: list[str] = []
        for section in sections:
            section = section.strip()
            if not section:
                continue

            if len(section) <= max_chars:
                chunks.append(section)
                continue

            # Step 2: split by double-newline (paragraphs)
            paragraphs = re.split(r"\n\n+", section)
            current_chunk = ""

            for para in paragraphs:
                para = para.strip()
                if not para:
                    continue

                if len(current_chunk) + len(para) + 2 <= max_chars:
                    current_chunk = f"{current_chunk}\n\n{para}" if current_chunk else para
                else:
                    if current_chunk:
                        chunks.append(current_chunk)
                    # If single paragraph exceeds max, split by sentences
                    if len(para) > max_chars:
                        sentences = re.split(r"(?<=[.!?])\s+", para)
                        sub_chunk = ""
                        for sent in sentences:
                            if len(sub_chunk) + len(sent) + 1 <= max_chars:
                                sub_chunk = f"{sub_chunk} {sent}" if sub_chunk else sent
                            else:
                                if sub_chunk:
                                    chunks.append(sub_chunk)
                                sub_chunk = sent
                        current_chunk = sub_chunk
                    else:
                        current_chunk = para

            if current_chunk:
                chunks.append(current_chunk)

        return chunks

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def query(
        self,
        text: str,
        top_k: int = 6,
        news_lambda: float = 0.05,
        fact_lambda: float = 0.005,
    ) -> list[dict]:
        """
        Search for knowledge chunks similar to the given text.

        Fetches 2×top_k from Pinecone, applies confidence decay based on
        chunk_type and ingested_at, re-sorts, and returns top_k results.

        Returns list of dicts with keys: id, score, adjusted_score, text, metadata.
        Returns empty list if keys are missing or on error.
        """
        if not self._keys_present:
            return []

        fetch_k = top_k * 2  # over-fetch to compensate for decay re-ranking

        try:
            embedding = await self._get_embedding(text)

            # SDK path
            if self._index is not None:
                results = self._index.query(
                    vector=embedding,
                    top_k=fetch_k,
                    include_metadata=True,
                )
                raw_matches = results.get("matches", [])
            else:
                # REST path
                host = await self._resolve_pinecone_host()
                async with httpx.AsyncClient(timeout=30) as client:
                    resp = await client.post(
                        f"https://{host}/query",
                        headers={
                            "Api-Key": self.pinecone_api_key,
                            "Content-Type": "application/json",
                        },
                        json={
                            "vector": embedding,
                            "topK": fetch_k,
                            "includeMetadata": True,
                        },
                    )
                    resp.raise_for_status()
                    data = resp.json()
                raw_matches = data.get("matches", [])

            # Apply confidence decay and re-rank
            items = []
            for match in raw_matches:
                meta = match.get("metadata", {})
                raw_score = match["score"]
                adjusted = self.apply_confidence_decay(
                    score=raw_score,
                    ingested_at=meta.get("ingested_at"),
                    chunk_type=meta.get("chunk_type", "fact"),
                    news_lambda=news_lambda,
                    fact_lambda=fact_lambda,
                )
                items.append({
                    "id": match["id"],
                    "score": raw_score,
                    "adjusted_score": adjusted,
                    "text": meta.get("text", ""),
                    "metadata": meta,
                })

            items.sort(key=lambda x: x["adjusted_score"], reverse=True)
            return items[:top_k]

        except Exception as exc:
            logger.error(f"RAG query error: {exc}")
            return []

    async def ingest(
        self,
        text: str,
        metadata: dict | None = None,
        chunk_type: str = "fact",
    ) -> str:
        """
        Add a knowledge chunk to the vector store.

        chunk_type: "news" (decays fast) or "fact" (decays slow).
        Returns the vector ID, or empty string on failure.
        """
        if not self._keys_present:
            return ""

        metadata = metadata or {}
        vector_id = str(uuid.uuid4())

        try:
            embedding = await self._get_embedding(text)

            # Store text + decay metadata
            store_metadata = {
                **metadata,
                "text": text,
                "chunk_type": chunk_type,
                "ingested_at": datetime.now(tz=timezone.utc).isoformat(),
            }

            # SDK path
            if self._index is not None:
                self._index.upsert(
                    vectors=[(vector_id, embedding, store_metadata)]
                )
                return vector_id

            # REST path
            host = await self._resolve_pinecone_host()
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    f"https://{host}/vectors/upsert",
                    headers={
                        "Api-Key": self.pinecone_api_key,
                        "Content-Type": "application/json",
                    },
                    json={
                        "vectors": [
                            {
                                "id": vector_id,
                                "values": embedding,
                                "metadata": store_metadata,
                            }
                        ]
                    },
                )
                resp.raise_for_status()

            return vector_id

        except Exception as exc:
            logger.error(f"RAG ingest error: {exc}")
            return ""

    async def ingest_file(self, filepath: Path, chunk_type: str = "fact") -> int:
        """
        Read a markdown file, split into chunks, ingest all.

        Returns the number of successfully ingested chunks.
        """
        if not self._keys_present:
            return 0

        try:
            text = filepath.read_text(encoding="utf-8")
        except Exception as exc:
            logger.error(f"Cannot read {filepath}: {exc}")
            return 0

        chunks = self.split_into_chunks(text)
        if not chunks:
            logger.warning(f"No chunks extracted from {filepath}")
            return 0

        file_hash = hashlib.sha256(str(filepath.name).encode()).hexdigest()[:12]
        ingested = 0

        for i, chunk in enumerate(chunks):
            metadata = {
                "source": filepath.name,
                "file_hash": file_hash,
                "chunk_index": i,
                "total_chunks": len(chunks),
            }
            vec_id = await self.ingest(chunk, metadata, chunk_type=chunk_type)
            if vec_id:
                ingested += 1

        logger.info(f"Ingested {ingested}/{len(chunks)} chunks from {filepath.name}")
        return ingested
