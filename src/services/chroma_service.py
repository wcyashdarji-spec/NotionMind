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
        self.is_clip = "clip" in model_name.lower()

        try:
            if self.is_clip:
                from src.services.clip_service import ClipService
                logger.info(f"Loading CLIP model '{model_name}' …")
                self.clip_service = ClipService(model_name)
                self.dimension = 512
                logger.info("CLIP model loaded – embedding dimension: 512.")
            else:
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
        Ingest documents and images into a Chroma vector collection.

        This method processes raw documents by splitting text into chunks,
        generating embeddings for both text and images, and storing the
        resulting vectors along with their metadata in the specified
        ChromaDB collection. The collection may optionally be recreated
        before ingestion begins.

        Args:
            documents: Raw documents to ingest.
            collection_name: Target Chroma collection.
            recreate: Whether to recreate the collection before ingestion.
            chunk_size: Maximum number of characters per text chunk.
            chunk_overlap: Number of overlapping characters between chunks.

        Returns:
            int:
                The total number of text chunks and image records stored.

        Raises:
            Exception:
                Propagates embedding, storage, or ChromaDB errors.
        """
        if not documents:
            logger.warning("ingest() called with an empty document list.")
            return 0

        try:
            await self.setup_collection(collection_name, recreate=recreate)

            chunks = self._prepare_chunks(documents, chunk_size, chunk_overlap)
            
            images_to_ingest = []
            for doc in documents:
                page_images = doc.get("images", [])
                for img in page_images:
                    images_to_ingest.append({
                        "id": f"{doc['page_id']}_image_{img['block_id']}",
                        "page_id": doc["page_id"],
                        "title": doc["title"],
                        "url": doc["url"],
                        "block_id": img["block_id"],
                        "local_path": img["local_path"],
                        "caption": img["caption"],
                        "original_url": img["original_url"],
                    })

            total_records = len(chunks) + len(images_to_ingest)
            if total_records == 0:
                logger.warning("No chunks or images produced; nothing to insert.")
                return 0

            logger.info(f"Encoding {len(chunks)} text chunk(s) …")
            if len(chunks) > 0:
                texts = [c["text"] for c in chunks]
                if self.is_clip:
                    text_embeddings = []
                    for t in texts:
                        emb = await asyncio.to_thread(self.clip_service.get_text_embedding, t)
                        text_embeddings.append(emb)
                else:
                    text_embeddings = await asyncio.to_thread(
                        self.model.encode,
                        texts,
                        show_progress_bar=False
                    )
                    text_embeddings = text_embeddings.tolist()

                for idx, emb in enumerate(text_embeddings):
                    chunks[idx]["text_dense"] = emb

            logger.info(f"Encoding {len(images_to_ingest)} image(s) …")
            if len(images_to_ingest) > 0:
                from PIL import Image
                for img_rec in images_to_ingest:
                    disk_path = img_rec["local_path"].lstrip("/")
                    try:
                        img_pil = Image.open(disk_path)
                        if self.is_clip:
                            emb = await asyncio.to_thread(self.clip_service.get_image_embedding, img_pil)
                        else:
                            logger.warning("CLIP is not enabled; using text embedding of caption as fallback for image.")
                            fallback_text = img_rec["caption"] or f"Image on page {img_rec['title']}"
                            emb_raw = await asyncio.to_thread(self.model.encode, fallback_text)
                            emb = emb_raw.tolist()
                        img_rec["text_dense"] = emb
                    except Exception as img_exc:
                        logger.error(f"Failed to load/embed image {disk_path}: {img_exc}")
                        img_rec["text_dense"] = None

                images_to_ingest = [img for img in images_to_ingest if img["text_dense"] is not None]

            collection = await asyncio.to_thread(
                self.client.get_or_create_collection,
                name=collection_name,
                metadata={"hnsw:space": "cosine"}
            )

            inserted = 0
            if len(chunks) > 0:
                for batch_start in range(0, len(chunks), _BATCH_SIZE):
                    batch = chunks[batch_start : batch_start + _BATCH_SIZE]
                    ids = [c["id"] for c in batch]
                    embeddings = [c["text_dense"] for c in batch]
                    metadatas = [{
                        "type": "text",
                        "page_id": c["page_id"],
                        "title": c["title"],
                        "url": c["url"],
                        "chunk_index": c["chunk_index"]
                    } for c in batch]
                    documents_list = [c["text"] for c in batch]

                    await asyncio.to_thread(
                        collection.upsert,
                        ids=ids,
                        embeddings=embeddings,
                        metadatas=metadatas,
                        documents=documents_list
                    )
                    inserted += len(batch)
                    logger.info(f"Ingested {len(batch)} text chunk(s) (total text chunks: {inserted}/{len(chunks)}).")

            img_inserted = 0
            if len(images_to_ingest) > 0:
                for batch_start in range(0, len(images_to_ingest), _BATCH_SIZE):
                    batch = images_to_ingest[batch_start : batch_start + _BATCH_SIZE]
                    ids = [c["id"] for c in batch]
                    embeddings = [c["text_dense"] for c in batch]
                    metadatas = [{
                        "type": "image",
                        "page_id": c["page_id"],
                        "title": c["title"],
                        "url": c["url"],
                        "block_id": c["block_id"],
                        "local_path": c["local_path"],
                        "original_url": c["original_url"],
                        "caption": c["caption"]
                    } for c in batch]
                    documents_list = [f"Image caption: {c['caption']}" for c in batch]

                    await asyncio.to_thread(
                        collection.upsert,
                        ids=ids,
                        embeddings=embeddings,
                        metadatas=metadatas,
                        documents=documents_list
                    )
                    img_inserted += len(batch)
                    logger.info(f"Ingested {len(batch)} image(s) (total images: {img_inserted}/{len(images_to_ingest)}).")

            logger.info(f"Ingestion complete: {inserted} text chunk(s) and {img_inserted} image(s) stored in '{collection_name}'.")
            return inserted + img_inserted

        except Exception as exc:
            logger.error(f"ingest() failed: {exc}")
            raise

    async def _get_cached_collection(self, collection_name: str) -> Any:
        """
        Retrieve a cached Chroma collection handle.

        This method returns an existing cached collection handle when
        available, avoiding repeated lookups to ChromaDB. If the handle is
        not already cached, it is loaded from the database, cached for
        future requests, and then returned.

        Args:
            collection_name: Name of the Chroma collection.

        Returns:
            Any:
                A ready-to-use Chroma collection handle.

        Raises:
            ValueError:
                If the requested collection does not exist.
            Exception:
                Propagates any errors encountered while loading the
                collection.
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
        Perform semantic similarity search on a Chroma collection.

        This method generates an embedding for the supplied query, performs
        a vector similarity search against the specified collection, and
        returns the most relevant text and image results together with
        their metadata and similarity scores.

        Args:
            query: Natural language search query.
            collection_name: Chroma collection to search.
            limit: Maximum number of matching results to return.

        Returns:
            List[Dict[str, Any]]:
                A list of matching documents and images ordered by
                similarity.

        Raises:
            ValueError:
                If the specified collection does not exist.
            Exception:
                Propagates embedding or ChromaDB search errors.
        """
        try:
            collection = await self._get_cached_collection(collection_name)

            logger.info(
                f"Chroma semantic search on '{collection_name}' | query='{query}' | limit={limit}"
            )

            if self.is_clip:
                dense_vector = await asyncio.to_thread(self.clip_service.get_text_embedding, query)
            else:
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
                    hit_metadata = metadatas[idx]
                    hit_type = hit_metadata.get("type", "text")
                    
                    res = {
                        "id": ids[idx],
                        "score": distances[idx],
                        "type": hit_type,
                        "page_id": hit_metadata.get("page_id"),
                        "title": hit_metadata.get("title"),
                        "url": hit_metadata.get("url"),
                    }
                    
                    if hit_type == "image":
                        res.update({
                            "block_id": hit_metadata.get("block_id"),
                            "local_path": hit_metadata.get("local_path"),
                            "original_url": hit_metadata.get("original_url"),
                            "caption": hit_metadata.get("caption"),
                            "text": documents_list[idx],
                        })
                    else:
                        import re
                        text_content = documents_list[idx]
                        
                        image_paths = re.findall(r'!\[.*?\]\((/static/images/.*?)\)', text_content)
                        
                        cleaned_text = re.sub(r'!\[.*?\]\((/static/images/.*?)\)', '', text_content)

                        cleaned_text = re.sub(r'\n{3,}', '\n\n', cleaned_text).strip()
                        
                        res.update({
                            "text": cleaned_text,
                            "chunk_index": hit_metadata.get("chunk_index"),
                            "images": image_paths,
                        })
                        
                    results.append(res)

            logger.info(f"Chroma semantic search returned {len(results)} result(s).")
            return results

        except Exception as exc:
            logger.error(f"search() failed: {exc}")
            raise

    async def delete_collection(self, collection_name: str) -> dict[str, Any]:
        """
        Delete a Chroma collection and its associated resources.

        This method removes the specified Chroma collection, deletes any
        locally stored image files referenced by the collection, clears the
        cached collection handle, and attempts to remove the underlying
        index folders from disk.

        Args:
            collection_name: Name of the collection to delete.

        Returns:
            dict[str, Any]:
                Summary information describing the deleted chunks, images,
                image files, and index folders.

        Raises:
            Exception:
                Propagates any errors encountered while deleting the
                collection and its associated resources.
        """
        import os
        import sqlite3
        import shutil

        deleted_chunks = 0
        deleted_images = 0
        deleted_image_files = []
        folders_to_delete = []

        try:
            sqlite_file = os.path.join(self.db_path, "chroma.sqlite3")
            if os.path.exists(sqlite_file):
                try:
                    conn = sqlite3.connect(sqlite_file)
                    cursor = conn.cursor()
                    cursor.execute("SELECT id FROM collections WHERE name = ?", (collection_name,))
                    col_row = cursor.fetchone()
                    if col_row:
                        col_id = col_row[0]
                        folders_to_delete.append(col_id)
                        try:
                            cursor.execute("SELECT id FROM segments WHERE collection = ?", (col_id,))
                            for row in cursor.fetchall():
                                folders_to_delete.append(row[0])
                        except sqlite3.OperationalError:
                            cursor.execute("SELECT id FROM segments WHERE collection_id = ?", (col_id,))
                            for row in cursor.fetchall():
                                folders_to_delete.append(row[0])
                    conn.close()
                    logger.info(f"Identified index folder(s) for collection '{collection_name}': {folders_to_delete}")
                except Exception as sql_exc:
                    logger.warning(f"Could not query Chroma SQLite database for collection folder cleanup: {sql_exc}")

            try:
                collection = await self._get_cached_collection(collection_name)
                results = await asyncio.to_thread(
                    collection.get,
                    include=["metadatas"]
                )
                if results and "metadatas" in results and results["metadatas"]:
                    deleted_chunks = len(results["metadatas"])
                    for metadata in results["metadatas"]:
                        if metadata and "local_path" in metadata:
                            local_path = metadata["local_path"]
                            disk_path = local_path.lstrip("/")
                            if os.path.exists(disk_path):
                                try:
                                    os.remove(disk_path)
                                    deleted_images += 1
                                    deleted_image_files.append(disk_path)
                                    logger.info(f"Deleted local image file: {disk_path}")
                                except Exception as img_exc:
                                    logger.error(f"Failed to delete local image file {disk_path}: {img_exc}")
            except ValueError:
                logger.warning(f"Chroma collection '{collection_name}' not found during deletion scan.")
            except Exception as scan_exc:
                logger.error(f"Error scanning collection '{collection_name}' for deletion: {scan_exc}")

            logger.info(f"Dropping Chroma collection '{collection_name}' …")
            try:
                await asyncio.to_thread(self.client.delete_collection, collection_name)
            except Exception as drop_exc:
                logger.debug(f"Drop collection '{collection_name}' error/warning: {drop_exc}")

            self._collection_cache.pop(collection_name, None)
            logger.info(f"Chroma collection '{collection_name}' deleted successfully.")

            deleted_folders = []
            for folder in folders_to_delete:
                folder_path = os.path.join(self.db_path, folder)
                if os.path.exists(folder_path):
                    logger.info(f"Attempting to remove Chroma index folder: {folder_path}")
                    try:
                        await asyncio.to_thread(shutil.rmtree, folder_path)
                        deleted_folders.append(folder)
                        logger.info(f"Successfully removed Chroma index folder from disk: {folder_path}")
                    except Exception as err:
                        logger.warning(f"Could not remove index folder {folder_path} (files may be locked): {err}")

            return {
                "chunks_deleted": deleted_chunks,
                "images_deleted": deleted_images,
                "image_files": deleted_image_files,
                "folders_deleted": deleted_folders
            }

        except Exception as exc:
            logger.error(f"delete_collection('{collection_name}') failed: {exc}")
            raise


