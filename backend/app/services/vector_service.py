import chromadb
from chromadb.config import Settings as ChromaSettings
from typing import List, Dict, Any
from app.core.config import settings
import logging
import re

logger = logging.getLogger(__name__)

def chunk_text(text: str, chunk_size: int = 250, overlap: int = 40) -> List[str]:
    """
    Splits text into chunks of specified word size with overlap.
    """
    words = text.strip().split()
    if not words:
        return []
    if len(words) <= chunk_size:
        return [" ".join(words)]

    chunks = []
    i = 0
    while i < len(words):
        chunk_words = words[i:i + chunk_size]
        chunks.append(" ".join(chunk_words))
        i += (chunk_size - overlap)
    return chunks

class VectorService:
    def __init__(self):
        try:
            self.client = chromadb.PersistentClient(path=settings.CHROMA_PERSIST_DIR)
            self.collection = self.client.get_or_create_collection(name="talent_sphere_documents")
            logger.info("VectorService initialized with persistent ChromaDB client.")
        except Exception as e:
            logger.error(f"Failed to initialize ChromaDB client: {e}")
            self.client = None
            self.collection = None

    def add_chunks(self, document_id: str, document_title: str, chunks: List[Dict[str, Any]]) -> List[str]:
        """
        Adds document text chunks to ChromaDB collection.
        Returns list of vector IDs.
        """
        if not self.collection:
            logger.warning("Vector collection unavailable. Add chunks skipped.")
            return []

        ids = []
        documents = []
        metadatas = []

        for chunk in chunks:
            vector_id = f"doc_{document_id}_chunk_{chunk['chunk_index']}"
            ids.append(vector_id)
            documents.append(chunk["content"])
            metadatas.append({
                "document_id": str(document_id),
                "document_title": str(document_title),
                "page_number": chunk.get("page_number", 1),
                "chunk_index": chunk.get("chunk_index", 0)
            })

        if ids:
            try:
                self.collection.add(
                    ids=ids,
                    documents=documents,
                    metadatas=metadatas
                )
                logger.info(f"Added {len(ids)} vector chunks for document '{document_title}' (ID: {document_id}).")
            except Exception as e:
                logger.error(f"Error adding chunks to ChromaDB: {e}")
                return []
        return ids

    def add_study_plan_lesson_vector(self, plan_id: str, week_id: str, day_id: str, day_number: int, lesson_title: str, lesson_content: str) -> List[str]:
        """
        Chunks and embeds a Study Plan Day lesson into ChromaDB vector store.
        Stores week_id, plan_id, day_id in metadata for RAG retrieval.
        """
        if not self.collection or not lesson_content or not lesson_content.strip():
            return []

        doc_id = f"sp_day_{day_id}"
        self.delete_document_chunks(doc_id)

        text_chunks = chunk_text(lesson_content, chunk_size=200, overlap=30)
        ids = []
        documents = []
        metadatas = []

        for idx, content_str in enumerate(text_chunks):
            v_id = f"{doc_id}_c{idx}"
            ids.append(v_id)
            documents.append(content_str)
            metadatas.append({
                "document_id": doc_id,
                "document_title": f"Day {day_number}: {lesson_title}",
                "week_id": str(week_id),
                "plan_id": str(plan_id),
                "day_id": str(day_id),
                "day_number": day_number,
                "chunk_index": idx
            })

        if ids:
            try:
                self.collection.add(
                    ids=ids,
                    documents=documents,
                    metadatas=metadatas
                )
                logger.info(f"ChromaDB: Added {len(ids)} embeddings for Study Plan Week '{week_id}' Day {day_number}.")
            except Exception as e:
                logger.error(f"ChromaDB: Error embedding Study Plan lesson: {e}")
                return []
        return ids

    def get_week_vectors(self, week_id: str) -> List[Dict[str, Any]]:
        """
        Retrieves all embedded lesson chunks from ChromaDB for a specific Study Plan Week.
        """
        if not self.collection:
            return []

        try:
            results = self.collection.get(
                where={"week_id": str(week_id)}
            )
            if results and results.get("documents"):
                retrieved = []
                docs = results["documents"]
                metas = results.get("metadatas", [])
                for i in range(len(docs)):
                    m = metas[i] if i < len(metas) else {}
                    retrieved.append({
                        "content": docs[i],
                        "day_number": m.get("day_number", 1),
                        "document_title": m.get("document_title", "Lesson")
                    })
                return retrieved
        except Exception as e:
            logger.error(f"Error querying week vectors from ChromaDB: {e}")
        return []

    def search_week_vectors(self, week_id: str, query_text: str, top_k: int = 4) -> List[Dict[str, Any]]:
        """
        Performs RAG similarity search on ChromaDB for a specific Study Plan Week.
        """
        if not self.collection or not query_text or not query_text.strip():
            return self.get_week_vectors(week_id)[:top_k]

        try:
            results = self.collection.query(
                query_texts=[query_text.strip()],
                n_results=top_k,
                where={"week_id": str(week_id)}
            )
            if results and results.get("documents") and results["documents"][0]:
                retrieved = []
                docs = results["documents"][0]
                metas = results["metadatas"][0] if results.get("metadatas") else []
                for i in range(len(docs)):
                    m = metas[i] if i < len(metas) else {}
                    retrieved.append({
                        "content": docs[i],
                        "day_number": m.get("day_number", 1),
                        "document_title": m.get("document_title", "Lesson")
                    })
                return retrieved
        except Exception as e:
            logger.error(f"Error executing vector search on week {week_id}: {e}")
        return self.get_week_vectors(week_id)[:top_k]

    def search_similar(self, query: str, top_k: int = 6) -> List[Dict[str, Any]]:
        """
        Performs vector similarity search on document chunks.
        """
        if not self.collection:
            logger.info("Vector search skipped: ChromaDB collection unavailable.")
            return []

        if not query or not query.strip():
            return []

        try:
            results = self.collection.query(
                query_texts=[query.strip()],
                n_results=top_k
            )
        except Exception as e:
            logger.error(f"ChromaDB search query error: {e}")
            return []

        search_results = []
        seen_contents = set()

        if results and results.get("documents") and results["documents"][0]:
            docs = results["documents"][0]
            metas = results["metadatas"][0]
            distances = results.get("distances", [[0]*len(docs)])[0]

            for i in range(len(docs)):
                content_str = docs[i].strip()
                content_hash = content_str[:150]
                if content_hash in seen_contents:
                    continue
                seen_contents.add(content_hash)

                meta = metas[i] if i < len(metas) else {}
                dist = distances[i] if i < len(distances) else 0.5
                score = round(max(0.0, 1.0 - (dist / 2.0)), 3)

                search_results.append({
                    "vector_id": results["ids"][0][i] if results.get("ids") else f"chunk_{i}",
                    "document_id": meta.get("document_id"),
                    "document_title": meta.get("document_title", "Document"),
                    "page_number": meta.get("page_number", 1),
                    "chunk_index": meta.get("chunk_index", 0),
                    "content": content_str,
                    "score": score,
                    "raw_distance": dist
                })

        search_results.sort(key=lambda x: x["score"], reverse=True)
        return search_results

    def delete_document_chunks(self, document_id: str):
        """
        Removes all chunks associated with a document ID from vector database.
        """
        if not self.collection:
            return
        try:
            self.collection.delete(where={"document_id": str(document_id)})
            logger.info(f"Deleted vector chunks for document ID: {document_id}")
        except Exception as e:
            logger.error(f"Error deleting chunks for document {document_id}: {e}")

vector_service = VectorService()
