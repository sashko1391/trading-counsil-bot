"""
Tests for OilRAGEngine and OilKnowledgeLoader.
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch, MagicMock
from pathlib import Path

from src.knowledge.rag_engine import OilRAGEngine


# ============================================================
# Fixtures
# ============================================================

SAMPLE_EMBEDDING = [0.1] * 1536

SAMPLE_QUERY_RESPONSE = {
    "matches": [
        {
            "id": "vec-001",
            "score": 0.92,
            "metadata": {"text": "Contango means futures > spot", "source": "fundamentals.md"},
        },
        {
            "id": "vec-002",
            "score": 0.85,
            "metadata": {"text": "Backwardation means spot > futures", "source": "fundamentals.md"},
        },
    ]
}

SAMPLE_UPSERT_RESPONSE = {"upsertedCount": 1}

SAMPLE_INDEXES_RESPONSE = {
    "indexes": [
        {"name": "oil-knowledge", "host": "oil-knowledge-abc123.svc.pinecone.io"}
    ]
}

SAMPLE_OPENAI_EMBED_RESPONSE = {
    "data": [{"embedding": SAMPLE_EMBEDDING, "index": 0}],
    "model": "text-embedding-3-small",
    "usage": {"prompt_tokens": 5, "total_tokens": 5},
}


def _make_engine(pinecone_key="test-pine-key", openai_key="test-oai-key"):
    """Create engine with mocked SDK init."""
    with patch.dict("sys.modules", {"pinecone": None}):
        engine = OilRAGEngine(
            pinecone_api_key=pinecone_key,
            openai_api_key=openai_key,
        )
    return engine


def _mock_httpx_response(json_data, status_code=200):
    """Create a mock httpx response."""
    mock_resp = MagicMock()
    mock_resp.json.return_value = json_data
    mock_resp.status_code = status_code
    mock_resp.raise_for_status = MagicMock()
    return mock_resp


# ============================================================
# Missing API key handling
# ============================================================

class TestMissingKeys:
    @pytest.mark.asyncio
    async def test_query_returns_empty_without_pinecone_key(self):
        engine = _make_engine(pinecone_key="", openai_key="test-key")
        result = await engine.query("contango vs backwardation")
        assert result == []

    @pytest.mark.asyncio
    async def test_query_returns_empty_without_openai_key(self):
        engine = _make_engine(pinecone_key="test-key", openai_key="")
        result = await engine.query("contango vs backwardation")
        assert result == []

    @pytest.mark.asyncio
    async def test_ingest_returns_empty_without_keys(self):
        engine = _make_engine(pinecone_key="", openai_key="")
        result = await engine.ingest("some text")
        assert result == ""

    @pytest.mark.asyncio
    async def test_ingest_file_returns_zero_without_keys(self):
        engine = _make_engine(pinecone_key="", openai_key="")
        result = await engine.ingest_file(Path("data/knowledge/fundamentals.md"))
        assert result == 0


# ============================================================
# Chunk splitting
# ============================================================

class TestChunkSplitting:
    def test_split_by_separator(self):
        text = "Section one\n\n---\n\nSection two\n\n---\n\nSection three"
        chunks = OilRAGEngine.split_into_chunks(text)
        assert len(chunks) == 3
        assert "Section one" in chunks[0]
        assert "Section two" in chunks[1]
        assert "Section three" in chunks[2]

    def test_split_long_section_by_paragraphs(self):
        # Create text with many paragraphs that exceed max_tokens
        paragraphs = [f"Paragraph {i}. " * 50 for i in range(10)]
        text = "\n\n".join(paragraphs)
        chunks = OilRAGEngine.split_into_chunks(text, max_tokens=100)
        assert len(chunks) > 1
        # Each chunk should be under max chars
        for chunk in chunks:
            assert len(chunk) <= 100 * 4 + 200  # some tolerance

    def test_empty_text_returns_empty(self):
        chunks = OilRAGEngine.split_into_chunks("")
        assert chunks == []

    def test_short_text_single_chunk(self):
        text = "Short knowledge snippet about oil trading."
        chunks = OilRAGEngine.split_into_chunks(text)
        assert len(chunks) == 1
        assert chunks[0] == text


# ============================================================
# Query (REST API path)
# ============================================================

class TestQuery:
    @pytest.mark.asyncio
    async def test_query_returns_results(self):
        engine = _make_engine()

        # Mock both the embedding call and the Pinecone query call
        embed_resp = _mock_httpx_response(SAMPLE_OPENAI_EMBED_RESPONSE)
        index_resp = _mock_httpx_response(SAMPLE_INDEXES_RESPONSE)
        query_resp = _mock_httpx_response(SAMPLE_QUERY_RESPONSE)

        with patch("src.knowledge.rag_engine.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            # First call: embedding, second: resolve host, third: query
            mock_client.post = AsyncMock(side_effect=[embed_resp, query_resp])
            mock_client.get = AsyncMock(return_value=index_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            results = await engine.query("What is contango?", top_k=2)

        assert len(results) == 2
        assert results[0]["id"] == "vec-001"
        assert results[0]["score"] == 0.92
        assert "adjusted_score" in results[0]
        assert "Contango" in results[0]["text"]
        assert results[0]["metadata"]["source"] == "fundamentals.md"

    @pytest.mark.asyncio
    async def test_query_handles_api_error(self):
        engine = _make_engine()

        with patch("src.knowledge.rag_engine.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(side_effect=Exception("API timeout"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            results = await engine.query("test query")

        assert results == []


# ============================================================
# Ingest
# ============================================================

class TestIngest:
    @pytest.mark.asyncio
    async def test_ingest_creates_vector(self):
        engine = _make_engine()

        embed_resp = _mock_httpx_response(SAMPLE_OPENAI_EMBED_RESPONSE)
        index_resp = _mock_httpx_response(SAMPLE_INDEXES_RESPONSE)
        upsert_resp = _mock_httpx_response(SAMPLE_UPSERT_RESPONSE)

        with patch("src.knowledge.rag_engine.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(side_effect=[embed_resp, upsert_resp])
            mock_client.get = AsyncMock(return_value=index_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            vec_id = await engine.ingest(
                "Contango means futures price > spot price",
                metadata={"source": "fundamentals.md"},
            )

        assert vec_id != ""
        assert len(vec_id) == 36  # UUID format

    @pytest.mark.asyncio
    async def test_ingest_handles_error(self):
        engine = _make_engine()

        with patch("src.knowledge.rag_engine.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(side_effect=Exception("Network error"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            vec_id = await engine.ingest("test text")

        assert vec_id == ""


# ============================================================
# Ingest File
# ============================================================

class TestIngestFile:
    @pytest.mark.asyncio
    async def test_ingest_file_splits_and_loads(self, tmp_path):
        engine = _make_engine()

        # Create a temp markdown file with multiple sections
        md_content = "Section A content here\n\n---\n\nSection B content here\n\n---\n\nSection C content here"
        md_file = tmp_path / "test_knowledge.md"
        md_file.write_text(md_content)

        embed_resp = _mock_httpx_response(SAMPLE_OPENAI_EMBED_RESPONSE)
        index_resp = _mock_httpx_response(SAMPLE_INDEXES_RESPONSE)
        upsert_resp = _mock_httpx_response(SAMPLE_UPSERT_RESPONSE)

        with patch("src.knowledge.rag_engine.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            # 3 chunks: embed + upsert for each = 6 calls total on post
            mock_client.post = AsyncMock(side_effect=[
                embed_resp, upsert_resp,
                embed_resp, upsert_resp,
                embed_resp, upsert_resp,
            ])
            mock_client.get = AsyncMock(return_value=index_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            count = await engine.ingest_file(md_file)

        assert count == 3

    @pytest.mark.asyncio
    async def test_ingest_file_nonexistent(self):
        engine = _make_engine()
        count = await engine.ingest_file(Path("/tmp/nonexistent_file.md"))
        assert count == 0

    @pytest.mark.asyncio
    async def test_ingest_file_empty(self, tmp_path):
        engine = _make_engine()
        md_file = tmp_path / "empty.md"
        md_file.write_text("")
        count = await engine.ingest_file(md_file)
        assert count == 0


# ============================================================
# Confidence Decay
# ============================================================

class TestConfidenceDecay:
    def test_news_decays_faster_than_facts(self):
        from datetime import timedelta
        now = datetime(2026, 3, 10, 12, 0, tzinfo=timezone.utc)
        ingested = (now - timedelta(hours=14)).isoformat()

        news_score = OilRAGEngine.apply_confidence_decay(
            0.9, ingested, chunk_type="news", now=now
        )
        fact_score = OilRAGEngine.apply_confidence_decay(
            0.9, ingested, chunk_type="fact", now=now
        )
        # News at ~14h with λ=0.05 → ~half. Facts at ~14h with λ=0.005 → ~93%
        assert news_score < fact_score
        assert news_score < 0.5  # roughly half
        assert fact_score > 0.8

    def test_no_decay_without_ingested_at(self):
        score = OilRAGEngine.apply_confidence_decay(0.9, None)
        assert score == 0.9

    def test_no_decay_at_zero_hours(self):
        now = datetime(2026, 3, 10, 12, 0, tzinfo=timezone.utc)
        score = OilRAGEngine.apply_confidence_decay(
            0.9, now.isoformat(), now=now
        )
        assert score == pytest.approx(0.9, abs=0.001)

    def test_invalid_timestamp_returns_original(self):
        score = OilRAGEngine.apply_confidence_decay(0.9, "not-a-date")
        assert score == 0.9


class TestIngestMetadata:
    @pytest.mark.asyncio
    async def test_ingested_at_in_metadata(self):
        engine = _make_engine()

        embed_resp = _mock_httpx_response(SAMPLE_OPENAI_EMBED_RESPONSE)
        index_resp = _mock_httpx_response(SAMPLE_INDEXES_RESPONSE)
        upsert_resp = _mock_httpx_response(SAMPLE_UPSERT_RESPONSE)

        captured_json = {}

        async def mock_post(url, **kwargs):
            if "upsert" in str(url):
                captured_json.update(kwargs.get("json", {}))
                return upsert_resp
            return embed_resp

        with patch("src.knowledge.rag_engine.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(side_effect=mock_post)
            mock_client.get = AsyncMock(return_value=index_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            await engine.ingest("test", chunk_type="news")

        vectors = captured_json.get("vectors", [{}])
        meta = vectors[0].get("metadata", {})
        assert "ingested_at" in meta
        assert meta["chunk_type"] == "news"

    @pytest.mark.asyncio
    async def test_chunk_type_defaults_to_fact(self):
        engine = _make_engine()

        embed_resp = _mock_httpx_response(SAMPLE_OPENAI_EMBED_RESPONSE)
        index_resp = _mock_httpx_response(SAMPLE_INDEXES_RESPONSE)
        upsert_resp = _mock_httpx_response(SAMPLE_UPSERT_RESPONSE)

        captured_json = {}

        async def mock_post(url, **kwargs):
            if "upsert" in str(url):
                captured_json.update(kwargs.get("json", {}))
                return upsert_resp
            return embed_resp

        with patch("src.knowledge.rag_engine.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(side_effect=mock_post)
            mock_client.get = AsyncMock(return_value=index_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            await engine.ingest("test text")

        vectors = captured_json.get("vectors", [{}])
        meta = vectors[0].get("metadata", {})
        assert meta["chunk_type"] == "fact"


# ============================================================
# OilKnowledgeLoader
# ============================================================

class TestOilKnowledgeLoader:
    @pytest.mark.asyncio
    async def test_load_all_skips_already_ingested(self, tmp_path):
        """Test that files with same content hash are skipped."""
        from src.knowledge.oil_knowledge_loader import OilKnowledgeLoader
        import json

        # Create a knowledge file
        md_file = tmp_path / "test.md"
        md_file.write_text("Test content\n\n---\n\nMore content")

        # Pre-populate tracker with same hash
        import hashlib
        content_hash = hashlib.sha256("Test content\n\n---\n\nMore content".encode()).hexdigest()[:16]
        tracker_file = tmp_path / ".ingested_tracker.json"
        tracker_file.write_text(json.dumps({"test.md": content_hash}))

        engine = _make_engine(pinecone_key="", openai_key="")
        loader = OilKnowledgeLoader(rag_engine=engine, knowledge_dir=tmp_path)

        stats = await loader.load_all()
        assert stats["skipped"] == 1
        assert stats["loaded"] == 0

    @pytest.mark.asyncio
    async def test_load_all_no_files(self, tmp_path):
        """Test behavior when no .md files exist."""
        from src.knowledge.oil_knowledge_loader import OilKnowledgeLoader
        engine = _make_engine(pinecone_key="", openai_key="")
        loader = OilKnowledgeLoader(rag_engine=engine, knowledge_dir=tmp_path)

        stats = await loader.load_all()
        assert stats["loaded"] == 0
        assert stats["skipped"] == 0
