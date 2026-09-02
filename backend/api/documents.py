"""Upload, list, download and delete expense documents.

Every route here loads the row and confirms it belongs to the caller before
doing anything. A document that is not yours returns 404 rather than 403:
"forbidden" would confirm it exists, which is itself a small leak.
"""
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from core.deps import get_current_user
from database import get_db
from models import Document, DocumentStatus, User
from schemas import DocumentList, DocumentOut
from services import storage

router = APIRouter(prefix="/documents", tags=["documents"])


def _owned_document(document_id: int, user: User, db: Session) -> Document:
    document = db.get(Document, document_id)
    if document is None or document.user_id != user.user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")
    return document


@router.post("/upload", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
async def upload(
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


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    document = _owned_document(document_id, current_user, db)
    path = document.file_path

    # Row first: a missing file with no row is invisible and harmless, while
    # a row pointing at a deleted file shows up as a broken download.
    db.delete(document)
    db.commit()
    storage.delete(path)
    return None
