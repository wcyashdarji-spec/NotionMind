from __future__ import annotations

import asyncio
from typing import Any, Dict, List

import chromadb
from sentence_transformers import SentenceTransformer

from src.utils import chunk_text
from src.config import EMBEDDING_MODEL_NAME, CHROMA_DB_PATH, logger

_BATCH_SIZE = 100


class ChromaService:
    """
    Service class for local ChromaDB operations.

    Handles collection setup, document chunking, dense-embedding generation,
    and semantic similarity search on local persistent storage.

    Attributes:
        db_path: Local folder path for ChromaDB storage.
        dimension: Dimensionality of the dense embedding vectors.
        model: Loaded :class:`SentenceTransformer` instance.
        client: Connected :class:`chromadb.PersistentClient` instance.
    """

    def __init__(
        self,
        db_path: str = CHROMA_DB_PATH,
        model_name: str = EMBEDDING_MODEL_NAME,
    ) -> None:
        """
        Load the embedding model and initialise the Chroma client.

        Args:
            db_path: Path to the local directory where ChromaDB files are saved.
            model_name: HuggingFace model identifier for sentence embeddings.

        Raises:
            RuntimeError: When the embedding model or Chroma client fails to load.
        """
        self.db_path = db_path

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
            logger.info(f"Initialising Chroma client at path: {self.db_path} …")
            self.client = chromadb.PersistentClient(path=self.db_path)
            logger.info("Chroma PersistentClient initialised.")
        except Exception as exc:
            logger.error(f"Chroma client initialisation failed: {exc}")
            raise RuntimeError(f"Chroma connection failed: {exc}") from exc

        self._collection_cache: dict[str, Any] = {}

    async def setup_collection(self, collection_name: str, recreate: bool = False) -> None:
        """
        Create or verify the Chroma collection used for storing document chunks.

        Dynamic metadata fields are natively supported by ChromaDB.
        Distance metric is set to Cosine Similarity.

        Args:
            collection_name: Name of the target Chroma collection.
            recreate: When ``True``, drops an existing collection before
                creating a fresh one.

        Raises:
            Exception: Propagates any ChromaDB error.
        """
        try:
            if recreate:
                logger.info(f"Dropping existing Chroma collection '{collection_name}' …")
                try:
                    await asyncio.to_thread(self.client.delete_collection, collection_name)
                except Exception as exc:
                    logger.debug(f"Drop collection '{collection_name}' warning: {exc}")

                self._collection_cache.pop(collection_name, None)

            await asyncio.to_thread(
                self.client.get_or_create_collection,
                name=collection_name,
                metadata={"hnsw:space": "cosine"}
            )
            logger.info(f"Chroma collection '{collection_name}' verified/created.")

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

    async def ingest(
        self,
        documents: List[Dict[str, Any]],
        collection_name: str,
        recreate: bool = False,
        chunk_size: int = 2000,
        chunk_overlap: int = 500,
    ) -> int:
        """
        Chunk, embed, and insert documents into the specified Chroma collection.

        Args:
            documents: Raw page documents from the Notion crawler.
            collection_name: Target Chroma collection name.
            recreate: Drop and recreate the collection before inserting.
            chunk_size: Max character count per chunk.
            chunk_overlap: Overlap character budget between chunks.

        Returns:
            Total number of chunk records inserted.

        Raises:
            Exception: Propagates ChromaDB or embedding errors.
        """
        if not documents:
            logger.warning("ingest() called with an empty document list.")
            return 0

        try:
            await self.setup_collection(collection_name, recreate=recreate)

            chunks = self._prepare_chunks(documents, chunk_size, chunk_overlap)
            if not chunks:
                logger.warning("No chunks produced; nothing to insert.")
                return 0

            logger.info(f"Encoding {len(chunks)} chunk(s) …")
            embeddings = await asyncio.to_thread(
                self.model.encode,
                [c["text"] for c in chunks],
                show_progress_bar=False
            )
            for idx, emb in enumerate(embeddings):
                chunks[idx]["text_dense"] = emb.tolist()

            collection = await asyncio.to_thread(
                self.client.get_or_create_collection,
                name=collection_name,
                metadata={"hnsw:space": "cosine"}
            )

            inserted = 0
            for batch_start in range(0, len(chunks), _BATCH_SIZE):
                batch = chunks[batch_start : batch_start + _BATCH_SIZE]
                
                ids = [c["id"] for c in batch]
                batch_embeddings = [c["text_dense"] for c in batch]
                metadatas = [{
                    "page_id": c["page_id"],
                    "title": c["title"],
                    "url": c["url"],
                    "chunk_index": c["chunk_index"]
                } for c in batch]
                documents_list = [c["text"] for c in batch]

                await asyncio.to_thread(
                    collection.upsert,
                    ids=ids,
                    embeddings=batch_embeddings,
                    metadatas=metadatas,
                    documents=documents_list
                )
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

    async def _get_cached_collection(self, collection_name: str) -> Any:
        """
        Return a cached collection handle, fetching it from ChromaDB only on the
        first call for a given *collection_name*.

        The cached handle is invalidated automatically when :meth:`setup_collection`
        recreates the collection.

        Args:
            collection_name: Name of the Chroma collection.

        Returns:
            A ready :class:`chromadb.Collection` handle.

        Raises:
            ValueError: If the collection does not exist in ChromaDB.
            Exception: Propagates ChromaDB errors.
        """
        if collection_name not in self._collection_cache:
            logger.debug(f"[Chroma] Cache miss – fetching handle for '{collection_name}'.")
            
            try:
                handle = await asyncio.to_thread(
                    self.client.get_collection,
                    name=collection_name,
                )
            except Exception as exc:
                raise ValueError(
                    f"Collection '{collection_name}' does not exist or could not be loaded: {exc}"
                ) from exc
            
            self._collection_cache[collection_name] = handle
            logger.info(f"[Chroma] Cache populated for '{collection_name}'.")
        else:
            logger.info(f"[Chroma] Cache hit – reusing handle for '{collection_name}'.")
        return self._collection_cache[collection_name]

    async def search(
        self,
        query: str,
        collection_name: str,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Execute semantic vector similarity search on the local collection.

        The collection handle is cached after the first call, eliminating two
        round-trips to ChromaDB (``list_collections`` + ``get_collection``) on
        every subsequent request.

        Args:
            query: Natural-language query string.
            collection_name: Chroma collection to search.
            limit: Maximum number of results to return.

        Returns:
            List of result dicts, each containing ``id``, ``score``,
            ``page_id``, ``title``, ``url``, ``text``, and ``chunk_index``.

        Raises:
            ValueError: When the collection does not exist.
            Exception: Propagates ChromaDB or embedding errors.
        """
        try:
            collection = await self._get_cached_collection(collection_name)

            logger.info(
                f"Chroma semantic search on '{collection_name}' | query='{query}' | limit={limit}"
            )

            dense_vector_raw = await asyncio.to_thread(self.model.encode, query)
            dense_vector = dense_vector_raw.tolist()

            raw = await asyncio.to_thread(
                collection.query,
                query_embeddings=[dense_vector],
                n_results=limit
            )

            results: List[Dict[str, Any]] = []
            if raw and "ids" in raw and len(raw["ids"]) > 0:
                ids = raw["ids"][0]
                distances = raw["distances"][0]
                metadatas = raw["metadatas"][0]
                documents_list = raw["documents"][0]

                for idx in range(len(ids)):

                    results.append(
                        {
                            "id": ids[idx],
                            "score": distances[idx],
                            "page_id": metadatas[idx].get("page_id"),
                            "title": metadatas[idx].get("title"),
                            "url": metadatas[idx].get("url"),
                            "text": documents_list[idx],
                            "chunk_index": metadatas[idx].get("chunk_index"),
                        }
                    )

            logger.info(f"Chroma semantic search returned {len(results)} result(s).")
            return results

        except Exception as exc:
            logger.error(f"search() failed: {exc}")
            raise
