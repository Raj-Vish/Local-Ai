"""Stage 4: the local vector database.

ChromaDB, persisted to disk under the project. Nothing leaves this machine:
no cloud vector service, no hosted index, no API key.

The security rule that governs this whole module
------------------------------------------------
Every vector carries the user_id of the person who uploaded the document, and
every search is filtered by it. That filter is applied here, from the user the
backend authenticated -- never from anything a client sent. A request cannot
ask to search another person's documents, because the caller does not get to
supply the user_id at all.

This is the same isolation rule the rest of the application follows, applied
to a second store. MySQL rows, files on disk and vectors are three places the
same document lives, and all three are scoped the same way.

Identifiers are deterministic
-----------------------------
A chunk's id is built from user, document and chunk index. Re-indexing a
document therefore overwrites exactly the vectors it wrote last time instead
of adding a second copy, which is what stops the index drifting out of step
with the documents table.
"""
import logging
import threading

from config import settings
from services.chunking import Chunk

log = logging.getLogger("uvicorn.error")

_lock = threading.Lock()
_client = None
_collection = None


class VectorStoreError(Exception):
    """Raised when the index cannot be reached or written."""


def chunk_id(user_id: int, document_id: int, index: int) -> str:
    """Deterministic, so re-indexing replaces rather than duplicates."""
    return f"u{user_id}-d{document_id}-c{index}"


def _connect():
    global _client, _collection
    if _collection is not None:
        return _collection

    with _lock:
        if _collection is not None:
            return _collection
        try:
            import chromadb
            from chromadb.config import Settings as ChromaSettings

            _client = chromadb.PersistentClient(
                path=settings.chroma_path,
                settings=ChromaSettings(anonymized_telemetry=False, allow_reset=False),
            )
            _collection = _client.get_or_create_collection(
                name=settings.CHROMA_COLLECTION,
                # Cosine, because the embedding model produces vectors whose
                # direction carries the meaning; magnitude is not informative.
                metadata={"hnsw:space": "cosine"},
                # No embedding function: vectors are produced by
                # services/embeddings.py so there is exactly one place that
                # decides which model is in use.
                embedding_function=None,
            )
        except Exception as exc:
            raise VectorStoreError(
                f"Could not open the vector index ({type(exc).__name__})."
            )
    return _collection


def available() -> bool:
    try:
        _connect()
        return True
    except VectorStoreError:
        return False


def index_chunks(
    *,
    user_id: int,
    document_id: int,
    filename: str,
    chunks: list[Chunk],
    vectors: list[list[float]],
) -> int:
    """Write one document's chunks. Returns how many vectors were stored.

    user_id comes from the authenticated caller, never from a request body.
    """
    if len(chunks) != len(vectors):
        raise VectorStoreError(
            f"{len(chunks)} chunks but {len(vectors)} vectors -- refusing to index."
        )
    if not chunks:
        return 0

    collection = _connect()
    try:
        collection.upsert(
            ids=[chunk_id(user_id, document_id, c.index) for c in chunks],
            embeddings=vectors,
            documents=[c.text for c in chunks],
            metadatas=[{
                # Every one of these is set by the server.
                "user_id": int(user_id),
                "document_id": int(document_id),
                "chunk_index": int(c.index),
                "start_line": int(c.start_line),
                "end_line": int(c.end_line),
                "filename": filename,
            } for c in chunks],
        )
    except Exception as exc:
        raise VectorStoreError(f"Could not write to the index ({type(exc).__name__}).")

    return len(chunks)


def delete_document(*, user_id: int, document_id: int) -> None:
    """Remove every vector for one document.

    Scoped by user as well as document. A document id alone would be enough
    given ids are unique, but a delete that names only the id is one refactor
    away from removing someone else's rows.
    """
    collection = _connect()
    try:
        collection.delete(where={
            "$and": [{"user_id": int(user_id)}, {"document_id": int(document_id)}]
        })
    except Exception as exc:
        raise VectorStoreError(f"Could not update the index ({type(exc).__name__}).")


def search(*, user_id: int, query_vector: list[float], top_k: int) -> list[dict]:
    """Nearest chunks belonging to this user. Never anyone else's.

    The where-clause is the isolation boundary: it is built here from the
    authenticated user_id, so there is no request shape that can widen it.
    """
    collection = _connect()
    top_k = max(1, min(int(top_k), settings.RAG_MAX_TOP_K))

    try:
        raw = collection.query(
            query_embeddings=[query_vector],
            n_results=top_k,
            where={"user_id": int(user_id)},
            include=["documents", "metadatas", "distances"],
        )
    except Exception as exc:
        raise VectorStoreError(f"Search failed ({type(exc).__name__}).")

    ids = (raw.get("ids") or [[]])[0]
    documents = (raw.get("documents") or [[]])[0]
    metadatas = (raw.get("metadatas") or [[]])[0]
    distances = (raw.get("distances") or [[]])[0]

    results = []
    for position, identifier in enumerate(ids):
        metadata = metadatas[position] or {}
        # Belt and braces: the where-clause already did this, but a result
        # that does not belong to the caller must never be returned, whatever
        # the index says.
        if int(metadata.get("user_id", -1)) != int(user_id):
            log.error("vector store: dropped a result not owned by user %s", user_id)
            continue
        distance = float(distances[position]) if position < len(distances) else None
        results.append({
            "chunk_id": identifier,
            "document_id": int(metadata.get("document_id", 0)),
            "chunk_index": int(metadata.get("chunk_index", 0)),
            "start_line": int(metadata.get("start_line", 0)),
            "end_line": int(metadata.get("end_line", 0)),
            "filename": metadata.get("filename", ""),
            "text": documents[position] if position < len(documents) else "",
            # Cosine distance -> similarity, so bigger means closer, which is
            # what a person reading a score expects.
            "score": None if distance is None else round(1.0 - distance, 4),
            "distance": None if distance is None else round(distance, 4),
        })
    return results


def count_for_user(user_id: int) -> int:
    """How many chunks this user has indexed. Used by tests and diagnostics."""
    collection = _connect()
    try:
        got = collection.get(where={"user_id": int(user_id)}, include=[])
        return len(got.get("ids") or [])
    except Exception as exc:
        raise VectorStoreError(f"Could not read the index ({type(exc).__name__}).")


def stats() -> dict:
    collection = _connect()
    try:
        return {
            "collection": settings.CHROMA_COLLECTION,
            "path": settings.chroma_path,
            "total_chunks": collection.count(),
        }
    except Exception as exc:
        raise VectorStoreError(f"Could not read the index ({type(exc).__name__}).")
