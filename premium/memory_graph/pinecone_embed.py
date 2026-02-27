"""
Pinecone Embedding — Premium Module
Feature flag: ENABLE_MEMORY_GRAPH=true
Embeds memories as vectors for semantic search.
"""
import os
from event_logging.event_logger import EventLogger

ENABLED = os.getenv("ENABLE_MEMORY_GRAPH", "false").lower() == "true"
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY", "")
PINECONE_ENV = os.getenv("PINECONE_ENV", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

logger = EventLogger()


class PineconeEmbed:
    """Embed and search memories in Pinecone."""

    def __init__(self):
        self.enabled = ENABLED
        self._index = None

    def is_configured(self) -> bool:
        return self.enabled and bool(PINECONE_API_KEY) and bool(OPENAI_API_KEY)

    def _get_index(self, index_name: str = "openchief-memory"):
        if not self.is_configured():
            return None
        if self._index is None:
            try:
                import pinecone  # type: ignore
                pinecone.init(api_key=PINECONE_API_KEY, environment=PINECONE_ENV)
                self._index = pinecone.Index(index_name)
            except ImportError:
                logger.log_event("pinecone_error", {"error": "pinecone package not installed"})
        return self._index

    def _embed(self, text: str) -> list:
        """Get embedding vector from OpenAI."""
        try:
            from openai import OpenAI  # type: ignore
            client = OpenAI(api_key=OPENAI_API_KEY)
            resp = client.embeddings.create(model="text-embedding-3-small", input=text)
            return resp.data[0].embedding
        except Exception as exc:
            logger.log_event("embed_error", {"error": str(exc)})
            return []

    def upsert(self, memory_id: str, text: str, metadata: dict = None) -> dict:
        index = self._get_index()
        if index is None:
            return {"status": "unconfigured"}
        vector = self._embed(text)
        if not vector:
            return {"status": "embed_failed"}
        try:
            index.upsert([(memory_id, vector, metadata or {})])
            return {"status": "ok"}
        except Exception as exc:
            logger.log_event("pinecone_error", {"error": str(exc)})
            return {"status": "error", "error": str(exc)}

    def query(self, text: str, top_k: int = 5) -> list:
        index = self._get_index()
        if index is None:
            return []
        vector = self._embed(text)
        if not vector:
            return []
        try:
            result = index.query(vector=vector, top_k=top_k, include_metadata=True)
            return result.get("matches", [])
        except Exception as exc:
            logger.log_event("pinecone_error", {"error": str(exc)})
            return []
