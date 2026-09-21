"""Upload, list, download and delete expense documents.

Every route here loads the row and confirms it belongs to the caller before
doing anything. A document that is not yours returns 404 rather than 403:
"forbidden" would confirm it exists, which is itself a small leak.
"""
from fastapi import (
    APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile, status,
)
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from core.deps import get_current_user
from database import get_db
from models import Document, DocumentStatus, User
from schemas import (
    DocumentList, DocumentOut, DocumentText, ExpenseProposalOut, ProposedFieldOut,
)
from services import document_pipeline, field_extraction, indexing, storage

router = APIRouter(prefix="/documents", tags=["documents"])


def _owned_document(document_id: int, user: User, db: Session) -> Document:
    document = db.get(Document, document_id)
    if document is None or document.user_id != user.user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")
    return document


@router.post("/upload", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
async def upload(
    background: BackgroundTasks,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        contents, mime, extension = await storage.read_and_validate(file)
    except storage.UploadRejected as rejected:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(rejected))

    digest = storage.checksum(contents)

    # Checked per user: two people who attended the same dinner may each
    # upload the same bill, but one person may not upload it twice.
    duplicate = db.execute(
        select(Document).where(
            Document.user_id == current_user.user_id,
            Document.checksum_sha256 == digest,
        )
    ).scalar_one_or_none()

    if duplicate is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"You already uploaded this file on "
                f"{duplicate.uploaded_at:%d %b %Y} as {duplicate.original_filename}."
            ),
        )

    stored_name, path = storage.save(current_user.user_id, contents, extension)

    document = Document(
        user_id=current_user.user_id,
        # Kept as a label only. It is never used to build a path, so a name
        # containing "../.." is harmless text.
        original_filename=file.filename or f"upload{extension}",
        stored_filename=stored_name,
        file_path=path,
        mime_type=mime,
        file_size=len(contents),
        checksum_sha256=digest,
        status=DocumentStatus.UPLOADED.value,
    )
    db.add(document)
    try:
        db.commit()
    except Exception:
        # The row is the record of truth; an orphaned file on disk with no
        # row would never be reachable or cleaned up.
        db.rollback()
        storage.delete(path)
        raise
    db.refresh(document)

    # Queued only after the commit succeeded, so the background task can never
    # look for a row that was rolled back. The upload responds immediately;
    # the client watches `status` move uploaded -> processing -> ready/failed.
    background.add_task(document_pipeline.extract_document, document.document_id)

    return document


@router.get("", response_model=DocumentList)
def list_documents(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = db.execute(
        select(Document)
        .where(Document.user_id == current_user.user_id)
        .order_by(Document.uploaded_at.desc())
    ).scalars().all()
    return DocumentList(items=[DocumentOut.model_validate(r) for r in rows], count=len(rows))


@router.get("/{document_id}", response_model=DocumentOut)
def get_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _owned_document(document_id, current_user, db)


@router.get("/{document_id}/file")
def download_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    document = _owned_document(document_id, current_user, db)
    try:
        path = storage.resolve_for_read(document.file_path, current_user.user_id)
    except storage.UploadRejected:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

    if not path.exists():
        # Row without a file: the disk was cleaned up behind the application.
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="This file is no longer on the server.",
        )

    return FileResponse(
        path,
        media_type=document.mime_type,
        # The name the person originally gave, with path separators and
        # control characters stripped. The file on disk keeps its UUID name.
        filename=storage.safe_download_name(document.original_filename),
    )


@router.get("/{document_id}/text", response_model=DocumentText)
def get_document_text(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """The text read out of this document, if extraction has finished.

    Ownership is checked exactly as it is for the file itself -- extracted
    text is the document's contents, so it carries the same isolation rule.
    """
    document = _owned_document(document_id, current_user, db)

    text = ""
    if document.extracted_text_path:
        try:
            path = storage.resolve_for_read(document.extracted_text_path, current_user.user_id)
        except storage.UploadRejected:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Extracted text not found."
            )
        text = storage.read_text(str(path))

    return DocumentText(
        document_id=document.document_id,
        original_filename=document.original_filename,
        status=document.status,
        ocr_used=document.ocr_used,
        error_message=document.error_message,
        char_count=len(text),
        text=text,
    )


@router.get("/{document_id}/propose-expense", response_model=ExpenseProposalOut)
def propose_expense(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Suggest expense fields from this document's text.

    Read-only on purpose. This creates nothing: it reads the extracted text,
    proposes four values with the evidence for each, and returns them. An
    expense exists only once a person has reviewed the suggestion and posted
    it to /expenses themselves, which is what makes it verified.
    """
    document = _owned_document(document_id, current_user, db)

    if document.status != DocumentStatus.READY.value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                document.error_message
                or "This document has not been read yet, so there is nothing to propose from."
            ),
        )

    if not document.extracted_text_path:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No extracted text is stored for this document.",
        )

    try:
        path = storage.resolve_for_read(document.extracted_text_path, current_user.user_id)
    except storage.UploadRejected:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

    proposal = field_extraction.propose(storage.read_text(str(path)))

    def out(name: str) -> ProposedFieldOut:
        return ProposedFieldOut(**vars(getattr(proposal, name)))

    return ExpenseProposalOut(
        document_id=document.document_id,
        original_filename=document.original_filename,
        amount=out("amount"),
        expense_date=out("expense_date"),
        vendor=out("vendor"),
        category=out("category"),
        unresolved=proposal.unresolved,
    )


@router.post("/{document_id}/extract", response_model=DocumentOut, status_code=status.HTTP_202_ACCEPTED)
def retry_extraction(
    document_id: int,
    background: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Run extraction again for one document.

    Useful after Tesseract is installed on a server that did not have it, and
    for documents uploaded before extraction existed at all.
    """
    document = _owned_document(document_id, current_user, db)
    if document.status == DocumentStatus.PROCESSING.value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This document is already being read.",
        )

    document.status = DocumentStatus.UPLOADED.value
    document.error_message = None
    db.commit()
    db.refresh(document)

    background.add_task(document_pipeline.extract_document, document.document_id)
    return document


@router.post("/{document_id}/index", status_code=status.HTTP_202_ACCEPTED)
def reindex_document(
    document_id: int,
    background: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Make this document searchable again.

    Needed after a change of embedding model, and for documents that were
    extracted before semantic search existed. Re-indexing replaces the old
    vectors rather than adding to them.
    """
    document = _owned_document(document_id, current_user, db)
    if document.status != DocumentStatus.READY.value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This document has no extracted text, so there is nothing to index.",
        )

    background.add_task(indexing.index_document, document.document_id)
    return {"document_id": document.document_id, "status": "indexing"}


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    document = _owned_document(document_id, current_user, db)
    path = document.file_path
    text_path = document.extracted_text_path
    owner_id = document.user_id

    # Row first: a missing file with no row is invisible and harmless, while
    # a row pointing at a deleted file shows up as a broken download.
    db.delete(document)
    db.commit()

    # A vector left behind would keep this document's contents findable by
    # search after the person deleted it -- the same leak as leaving the file.
    indexing.remove_document(owner_id, document_id)
    storage.delete(path)
    # The extracted text is a copy of the document's contents, so deleting the
    # document must take it too -- otherwise a "deleted" receipt is still
    # readable on disk.
    if text_path:
        storage.delete(text_path)
    return None
