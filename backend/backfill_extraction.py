"""Run text extraction over documents that were uploaded before it existed.

    ./venv/bin/python backfill_extraction.py            # what would happen
    ./venv/bin/python backfill_extraction.py --apply    # actually do it
    ./venv/bin/python backfill_extraction.py --apply --retry-failed

Safe to stop and re-run: a document that is already "ready" is skipped unless
--force is given. Runs one document at a time on purpose -- OCR is the most
memory-hungry thing this project does, and this laptop has little to spare.
"""
import argparse
import sys

from database import SessionLocal
from models import Document, DocumentStatus
from services import document_pipeline, extraction


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="do it, rather than just listing")
    parser.add_argument("--retry-failed", action="store_true", help="include documents that failed before")
    parser.add_argument("--force", action="store_true", help="re-extract even documents already ready")
    parser.add_argument("--limit", type=int, default=0, help="stop after this many (0 = no limit)")
    args = parser.parse_args()

    wanted = {DocumentStatus.UPLOADED.value}
    if args.retry_failed:
        wanted.add(DocumentStatus.FAILED.value)
    if args.force:
        wanted |= {DocumentStatus.READY.value, DocumentStatus.PROCESSING.value}

    db = SessionLocal()
    try:
        rows = (
            db.query(Document)
            .filter(Document.status.in_(wanted))
            .order_by(Document.document_id)
            .all()
        )
        targets = [(d.document_id, d.original_filename, d.mime_type, d.status) for d in rows]
    finally:
        db.close()

    if args.limit:
        targets = targets[: args.limit]

    print(f"Tesseract available: {extraction.tesseract_available()}")
    print(f"poppler available:   {extraction.poppler_available()}")
    print(f"Documents selected:  {len(targets)}\n")

    if not targets:
        print("  Nothing to do.")
        return 0

    for doc_id, name, mime, status in targets:
        print(f"  [{doc_id}] {name}  ({mime}, was: {status})")

    if not args.apply:
        print("\nDRY RUN. Re-run with --apply to extract these.")
        return 0

    print()
    ok = failed = 0
    for doc_id, name, _mime, _status in targets:
        document_pipeline.extract_document(doc_id)
        db = SessionLocal()
        try:
            after = db.get(Document, doc_id)
            state = after.status if after else "gone"
            note = f" -- {after.error_message}" if after and after.error_message else ""
        finally:
            db.close()
        if state == DocumentStatus.READY.value:
            ok += 1
        else:
            failed += 1
        print(f"  [{doc_id}] {name}: {state}{note}")

    print(f"\n  {ok} extracted, {failed} failed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
