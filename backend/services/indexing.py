"""Stage 5: the pipeline that makes a document searchable.

    document -> extracted text -> chunks -> embeddings -> ChromaDB

It attaches to the end of extraction rather than replacing any of it. Stage 1
still does exactly what it did; when a document reaches "ready", this runs
afterwards. If indexing fails, the document is still uploaded, still readable
and still usable for an expense -- only semantic search is missing, and the
row says why.

Re-indexing is safe by construction: the existing vectors for a document are
deleted before new ones are written, so a document whose text changed, or
which produced fewer chunks the second time, cannot leave orphans behind.
"""
import logging
from dataclasses import dataclass
from datetime import datetime

from config import settings
from database import SessionLocal
from models import Document, DocumentIndex, DocumentStatus, IndexStatus
from services import chunking, embeddings, storage, vector_store

log = logging.getLogger("uvicorn.error")


@dataclass
class IndexResult:
    document_id: int
    status: str
    chunk_count: int = 0
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.status == IndexStatus.INDEXED.value


def _record(db, document: Document, status: IndexStatus, *, chunks: int = 0,
            error: str | None = None) -> None:
    """Create or update this document's index row."""
    row = db.get(DocumentIndex, document.document_id)
    if row is None:
        row = DocumentIndex(document_id=document.document_id, user_id=document.user_id)
        db.add(row)
    row.user_id = document.user_id          # keep in step if it ever moved
    row.status = status.value
    row.chunk_count = chunks
    row.embed_model = settings.EMBED_MODEL
    row.error_message = error
    row.indexed_at = datetime.now() if status is IndexStatus.INDEXED else None
    db.commit()


def index_document(document_id: int) -> IndexResult:
    """Chunk, embed and store one document. Never raises.

    Runs as a background task, detached from any request, so a failure has
    nowhere useful to propagate. It is written to the index row instead.
    """
    db = SessionLocal()
    try:
        document = db.get(Document, document_id)
        if document is None:
            log.warning("indexing: document %s vanished before indexing", document_id)
            return IndexResult(document_id, IndexStatus.FAILED.value,
                               error="Document no longer exists.")

        if document.status != DocumentStatus.READY.value or not document.extracted_text_path:
            message = "This document has no extracted text to index."
            _record(db, document, IndexStatus.FAILED, error=message)
            return IndexResult(document_id, IndexStatus.FAILED.value, error=message)

        text = storage.read_text(document.extracted_text_path)
        if not text.strip():
            message = "The extracted text is empty."
            _record(db, document, IndexStatus.FAILED, error=message)
            return IndexResult(document_id, IndexStatus.FAILED.value, error=message)

        chunks = chunking.chunk_document(text)
        if not chunks:
            message = "This document produced no chunks."
            _record(db, document, IndexStatus.FAILED, error=message)
            return IndexResult(document_id, IndexStatus.FAILED.value, error=message)

        try:
            vectors = embeddings.embed_texts([c.text for c in chunks])
        except embeddings.EmbeddingError as exc:
            _record(db, document, IndexStatus.FAILED, error=str(exc))
            return IndexResult(document_id, IndexStatus.FAILED.value, error=str(exc))

        try:
            # Delete first: a re-index that produced fewer chunks would
            # otherwise leave the surplus behind, still searchable.
            vector_store.delete_document(user_id=document.user_id,
                                         document_id=document.document_id)
            stored = vector_store.index_chunks(
                user_id=document.user_id,
                document_id=document.document_id,
                filename=document.original_filename,
                chunks=chunks,
                vectors=vectors,
            )
        except vector_store.VectorStoreError as exc:
            _record(db, document, IndexStatus.FAILED, error=str(exc))
            return IndexResult(document_id, IndexStatus.FAILED.value, error=str(exc))

        _record(db, document, IndexStatus.INDEXED, chunks=stored)
        log.info("indexing: document %s indexed as %d chunk(s)", document_id, stored)
        return IndexResult(document_id, IndexStatus.INDEXED.value, chunk_count=stored)

    except Exception as exc:
        log.exception("indexing: document %s raised %s", document_id, type(exc).__name__)
        return IndexResult(document_id, IndexStatus.FAILED.value,
                           error=f"Unexpected problem while indexing ({type(exc).__name__}).")
    finally:
        db.close()


def remove_document(user_id: int, document_id: int) -> None:
    """Forget a document: its vectors and its index row.

    Called when a document is deleted. A vector left behind would keep the
    document's contents searchable after the person deleted it, which is the
    same leak as leaving the file on disk.
    """
    try:
        vector_store.delete_document(user_id=user_id, document_id=document_id)
    except vector_store.VectorStoreError as exc:
        log.error("indexing: could not remove vectors for document %s -- %s", document_id, exc)

    db = SessionLocal()
    try:
        row = db.get(DocumentIndex, document_id)
        if row is not None:
            db.delete(row)
            db.commit()
    finally:
        db.close()
