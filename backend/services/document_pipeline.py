"""Coordinates what happens to a document after it is uploaded.

Stage 1 is text extraction. Stages 2-4 (chunking, embeddings, retrieval)
attach here later, which is why this is a separate module from extraction.py:
that one only knows how to read a file, this one knows what the application
does with the result.

Runs as a FastAPI background task, so it opens its own database session --
the request's session is already closed by the time this starts.
"""
import logging

from database import SessionLocal
from models import Document, DocumentStatus
from services import extraction, indexing, storage

log = logging.getLogger("uvicorn.error")


def _set_status(db, document: Document, status: DocumentStatus, error: str | None = None) -> None:
    document.status = status.value
    document.error_message = error
    db.commit()


def extract_document(document_id: int) -> None:
    """Read one document into text and record the outcome.

    Never raises: this runs detached from any request, so an exception here
    would only reach a log nobody is watching. Failures are written to the
    row instead, where the uploader can actually see them.
    """
    db = SessionLocal()
    try:
        document = db.get(Document, document_id)
        if document is None:
            log.warning("extraction: document %s vanished before processing", document_id)
            return

        _set_status(db, document, DocumentStatus.PROCESSING)

        try:
            result = extraction.extract(document.file_path, document.mime_type)
        except extraction.ExtractionError as rejected:
            log.info("extraction: document %s failed -- %s", document_id, rejected)
            _set_status(db, document, DocumentStatus.FAILED, str(rejected))
            return
        except Exception as exc:
            # An unexpected fault must not leave the row stuck on "processing"
            # forever, which would look like a hang with no explanation.
            log.exception("extraction: document %s raised %s", document_id, type(exc).__name__)
            _set_status(
                db, document, DocumentStatus.FAILED,
                f"Unexpected problem while reading this file ({type(exc).__name__}).",
            )
            return

        if not result.text:
            _set_status(
                db, document, DocumentStatus.FAILED,
                "No readable text was found in this file.",
            )
            return

        document.extracted_text_path = storage.save_text(
            document.user_id, document.stored_filename, result.text
        )
        document.ocr_used = result.ocr_used
        _set_status(db, document, DocumentStatus.READY)

        log.info(
            "extraction: document %s ready -- %d chars, %d page(s), ocr=%s",
            document_id, len(result.text), result.pages, result.ocr_used,
        )
    finally:
        db.close()

    # Stage 5, deliberately after the session above is closed and the document
    # is already usable. Indexing is an enhancement: if it fails the document
    # is still uploaded, readable and available for an expense.
    outcome = indexing.index_document(document_id)
    if not outcome.ok:
        log.warning("indexing: document %s not searchable -- %s", document_id, outcome.error)
