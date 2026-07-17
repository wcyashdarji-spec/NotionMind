from __future__ import annotations

from typing import Any, Dict, List

from pymilvus import (
    AnnSearchRequest,
    DataType,
    Function,
    FunctionType,
    MilvusClient,
    RRFRanker,
)
from sentence_transformers import SentenceTransformer

from src.utils import chunk_text
from src.config import EMBEDDING_MODEL_NAME, MILVUS_ENDPOINT, MILVUS_TOKEN, logger

_BATCH_SIZE = 100


class MilvusService:
    """
    Service class for Zilliz Milvus operations.

    Handles collection setup, document chunking, dense-embedding generation,
    and hybrid (dense + BM25 sparse) similarity search with RRF reranking.

    Attributes:
        uri: Milvus cluster endpoint URL.
        token: API key for authentication.
        dimension: Dimensionality of the dense embedding vectors.
        model: Loaded :class:`SentenceTransformer` instance.
        client: Connected :class:`MilvusClient` instance.
    """

    def __init__(
        self,
        uri: str = MILVUS_ENDPOINT,
        token: str = MILVUS_TOKEN,
        model_name: str = EMBEDDING_MODEL_NAME,
    ) -> None:
        """
        Load the embedding model and initialise the Milvus client.

        Args:
            uri: Milvus cluster public endpoint.
            token: Milvus API key / bearer token.
            model_name: HuggingFace model identifier for sentence embeddings.

        Raises:
            RuntimeError: When the embedding model or Milvus client fails to load.
        """
        self.uri = uri
        self.token = token

        try:
            logger.info(f"Loading embedding model '{model_name}' …")
            self.model: SentenceTransformer = SentenceTransformer(model_name)
            probe = self.model.encode("probe")
            self.dimension: int = len(probe)
            logger.info(f"Model loaded – embedding dimension: {self.dimension}.")
        except Exception as exc:
            logger.error(f"Failed to load embedding model '{model_name}': {exc}")
            raise RuntimeError(f"Embedding model load failed: {exc}") from exc

        try:
            if not self.uri or not self.token:
                logger.warning("MILVUS_ENDPOINT or MILVUS_TOKEN is not set.")
            self.client: MilvusClient = MilvusClient(uri=self.uri, token=self.token)
            logger.info("MilvusClient connected.")
        except Exception as exc:
            logger.error(f"MilvusClient initialisation failed: {exc}")
            raise RuntimeError(f"Milvus connection failed: {exc}") from exc


    def setup_collection(self, collection_name: str, recreate: bool = False) -> None:
        """
        Create or verify the Milvus collection used for storing document chunks.

        The collection schema contains:
        - ``id`` (VARCHAR primary key)
        - ``text`` (VARCHAR, analyzer-enabled for BM25)
        - ``text_dense`` (FLOAT_VECTOR for semantic search)
        - ``text_sparse`` (SPARSE_FLOAT_VECTOR populated by BM25 function)

        Dynamic fields are enabled so that metadata (``page_id``, ``title``,
        ``url``, ``chunk_index``) can be stored without explicit schema columns.

        Args:
            collection_name: Name of the target Milvus collection.
            recreate: When ``True``, drops an existing collection before
                creating a fresh one.

        Raises:
            Exception: Propagates any Milvus SDK error.
        """
        try:
            if recreate and self.client.has_collection(collection_name):
                logger.info(f"Dropping existing collection '{collection_name}' …")
                self.client.drop_collection(collection_name)

            if self.client.has_collection(collection_name):
                logger.info(f"Collection '{collection_name}' already exists.")
                return

            logger.info(f"Creating collection '{collection_name}' …")

            schema = self.client.create_schema(auto_id=False, enable_dynamic_field=True)
            schema.add_field("id", DataType.VARCHAR, max_length=128, is_primary=True)
            schema.add_field("text", DataType.VARCHAR, max_length=65535, enable_analyzer=True)
            schema.add_field("text_dense", DataType.FLOAT_VECTOR, dim=self.dimension)
            schema.add_field("text_sparse", DataType.SPARSE_FLOAT_VECTOR)

            schema.add_function(
                Function(
                    name="text_bm25_emb",
                    input_field_names=["text"],
                    output_field_names=["text_sparse"],
                    function_type=FunctionType.BM25,
                )
            )

            index_params = self.client.prepare_index_params()
            index_params.add_index(
                field_name="text_dense",
                index_name="idx_text_dense",
                index_type="AUTOINDEX",
                metric_type="COSINE",
            )
            index_params.add_index(
                field_name="text_sparse",
                index_name="idx_text_sparse",
                index_type="SPARSE_INVERTED_INDEX",
                metric_type="BM25",
                params={"inverted_index_algo": "DAAT_MAXSCORE"},
            )

            self.client.create_collection(
                collection_name=collection_name,
                schema=schema,
                index_params=index_params,
            )
            logger.info(f"Collection '{collection_name}' created with hybrid search schema.")

        except Exception as exc:
            logger.error(f"setup_collection('{collection_name}') failed: {exc}")
            raise


    def _prepare_chunks(
        self,
        documents: List[Dict[str, Any]],
        chunk_size: int = 2000,
        chunk_overlap: int = 500,
    ) -> List[Dict[str, Any]]:
        """
        Split raw page documents into overlapping text chunks with metadata.

        Args:
            documents: List of dicts with keys ``page_id``, ``title``,
                ``content``, and ``url``.
            chunk_size: Max characters per chunk.
            chunk_overlap: Overlap characters between consecutive chunks.

        Returns:
            List of chunk dicts ready for embedding and insertion.

        Raises:
            Exception: Propagates errors from :func:`~src.utils.chunk_text`.
        """
        result: List[Dict[str, Any]] = []
        try:
            for doc in documents:
                page_id = doc["page_id"]
                title = doc["title"]
                url = doc["url"]
                chunks = chunk_text(doc["content"], chunk_size, chunk_overlap)
                logger.info(f"  '{title}' → {len(chunks)} chunk(s).")
                for idx, chunk in enumerate(chunks):
                    result.append(
                        {
                            "id": f"{page_id}_{idx}",
                            "page_id": page_id,
                            "title": title,
                            "url": url,
                            "text": chunk,
                            "chunk_index": idx,
                        }
                    )
        except Exception as exc:
            logger.error(f"_prepare_chunks failed: {exc}")
            raise
        return result

    def ingest(
        self,
        documents: List[Dict[str, Any]],
        collection_name: str,
        recreate: bool = False,
        chunk_size: int = 2000,
        chunk_overlap: int = 500,
    ) -> int:
        """
        Chunk, embed, and insert documents into the specified Milvus collection.

        Args:
            documents: Raw page documents from the Notion crawler.
            collection_name: Target Milvus collection name.
            recreate: Drop and recreate the collection before inserting.
            chunk_size: Max character count per chunk.
            chunk_overlap: Overlap character budget between chunks.

        Returns:
            Total number of chunk records inserted.

        Raises:
            Exception: Propagates Milvus SDK or embedding errors.
        """
        if not documents:
            logger.warning("ingest() called with an empty document list.")
            return 0

        try:
            self.setup_collection(collection_name, recreate=recreate)

            chunks = self._prepare_chunks(documents, chunk_size, chunk_overlap)
            if not chunks:
                logger.warning("No chunks produced; nothing to insert.")
                return 0

            logger.info(f"Encoding {len(chunks)} chunk(s) …")
            embeddings = self.model.encode(
                [c["text"] for c in chunks], show_progress_bar=False
            )
            for idx, emb in enumerate(embeddings):
                chunks[idx]["text_dense"] = emb.tolist()

            inserted = 0
            for batch_start in range(0, len(chunks), _BATCH_SIZE):
                batch = chunks[batch_start : batch_start + _BATCH_SIZE]
                self.client.insert(collection_name=collection_name, data=batch)
                inserted += len(batch)
                logger.info(
                    f"Batch {batch_start // _BATCH_SIZE + 1}: "
                    f"inserted {len(batch)} record(s) "
                    f"(total: {inserted}/{len(chunks)})."
                )

            logger.info(f"Ingestion complete – {inserted} chunk(s) stored in '{collection_name}'.")
            return inserted

        except Exception as exc:
            logger.error(f"ingest() failed: {exc}")
            raise


    def search(
        self,
        query: str,
        collection_name: str,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Execute a multi-vector hybrid search combining dense semantic and BM25
        sparse keyword signals, reranked with Reciprocal Rank Fusion.

        Args:
            query: Natural-language query string.
            collection_name: Milvus collection to search.
            limit: Maximum number of results to return.

        Returns:
            List of result dicts, each containing ``id``, ``score``,
            ``page_id``, ``title``, ``url``, ``text``, and ``chunk_index``.

        Raises:
            ValueError: When the collection does not exist.
            Exception: Propagates Milvus SDK or embedding errors.
        """
        try:
            if not self.client.has_collection(collection_name):
                raise ValueError(f"Collection '{collection_name}' does not exist.")

            logger.info(
                f"Hybrid search on '{collection_name}' | query='{query}' | limit={limit}"
            )

            dense_vector = self.model.encode(query).tolist()

            request_dense = AnnSearchRequest(
                data=[dense_vector],
                anns_field="text_dense",
                param={"metric_type": "COSINE"},
                limit=limit,
            )
            request_sparse = AnnSearchRequest(
                data=[query],
                anns_field="text_sparse",
                param={},
                limit=limit,
            )

            raw = self.client.hybrid_search(
                collection_name=collection_name,
                reqs=[request_dense, request_sparse],
                ranker=RRFRanker(k=60),
                limit=limit,
                output_fields=["page_id", "title", "url", "text", "chunk_index"],
            )

            results: List[Dict[str, Any]] = []
            for hit in (raw[0] if raw else []):
                entity = hit.get("entity", {})
                results.append(
                    {
                        "id": hit.get("id"),
                        "score": hit.get("distance"),
                        "page_id": entity.get("page_id"),
                        "title": entity.get("title"),
                        "url": entity.get("url"),
                        "text": entity.get("text"),
                        "chunk_index": entity.get("chunk_index"),
                    }
                )

            logger.info(f"Hybrid search returned {len(results)} result(s).")
            return results

        except Exception as exc:
            logger.error(f"search() failed: {exc}")
            raise

