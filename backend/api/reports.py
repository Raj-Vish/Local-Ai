"""Expense report generation and download.

A report is a snapshot, not a live view. Each amount is copied into
expense_report_items at generation time, so correcting an expense next month
cannot silently change a report that has already been submitted.
"""
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from core.deps import get_current_user
from database import get_db
from models import Document, Expense, ExpenseReport, ExpenseReportItem, ReportStatus, User
from schemas import ReportDetail, ReportGenerate, ReportItemOut, ReportList, ReportOut
from services import report_builder, storage

router = APIRouter(prefix="/reports", tags=["reports"])

XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _owned_report(report_id: int, user: User, db: Session) -> ExpenseReport:
    report = db.get(ExpenseReport, report_id)
    if report is None or report.user_id != user.user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found.")
    return report


def _with_count(report: ExpenseReport, db: Session) -> ReportOut:
    out = ReportOut.model_validate(report)
    out.item_count = db.query(ExpenseReportItem).filter_by(report_id=report.report_id).count()
    return out


@router.post("/generate", response_model=ReportDetail, status_code=status.HTTP_201_CREATED)
def generate(
    payload: ReportGenerate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    expenses = db.execute(
        select(Expense)
        .where(
            Expense.user_id == current_user.user_id,
            Expense.expense_date >= payload.period_start,
            Expense.expense_date <= payload.period_end,
            # Only confirmed rows. Nothing an extractor guessed from a blurry
            # photo can reach a submitted claim without a human agreeing to it.
            Expense.is_verified.is_(True),
        )
        .order_by(Expense.expense_date, Expense.expense_id)
    ).scalars().all()

    if not expenses:
        # An empty report is worse than none: it could be attached to a claim
        # without anyone noticing it says nothing.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No confirmed expenses found for that period.",
        )

    total = report_builder.grand_total(expenses)

    report = ExpenseReport(
        user_id=current_user.user_id,
        report_name=payload.report_name,
        period_start=payload.period_start,
        period_end=payload.period_end,
        total_amount=total,
        currency=expenses[0].currency,
        status=ReportStatus.GENERATED.value,
        generated_at=datetime.now(),
    )
    db.add(report)
    db.flush()  # assigns report_id without committing yet

    for expense in expenses:
        db.add(
            ExpenseReportItem(
                report_id=report.report_id,
                expense_id=expense.expense_id,
                # Copied, not looked up. This is what freezes the report.
                amount_at_generation=expense.amount,
            )
        )

    document_ids = {e.document_id for e in expenses if e.document_id}
    names = {}
    if document_ids:
        rows = db.execute(
            select(Document.document_id, Document.original_filename).where(
                Document.document_id.in_(document_ids),
                Document.user_id == current_user.user_id,
            )
        ).all()
        names = {doc_id: filename for doc_id, filename in rows}

    try:
        path = report_builder.build_workbook(
            user=current_user,
            report_name=payload.report_name,
            period_start=payload.period_start,
            period_end=payload.period_end,
            expenses=expenses,
            document_names=names,
            currency=report.currency,
        )
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not build the report file.",
        )

    report.file_path = str(path)
    try:
        db.commit()
    except Exception:
        db.rollback()
        storage.delete(str(path))  # no orphan file without a row
        raise
    db.refresh(report)

    detail = ReportDetail.model_validate(report)
    detail.item_count = len(expenses)
    detail.items = [
        ReportItemOut.model_validate(i)
        for i in db.query(ExpenseReportItem).filter_by(report_id=report.report_id).all()
    ]
    return detail


@router.get("", response_model=ReportList)
def list_reports(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = db.execute(
        select(ExpenseReport)
        .where(ExpenseReport.user_id == current_user.user_id)
        .order_by(ExpenseReport.created_at.desc())
    ).scalars().all()
    return ReportList(items=[_with_count(r, db) for r in rows], count=len(rows))


@router.get("/{report_id}", response_model=ReportDetail)
def get_report(
    report_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    report = _owned_report(report_id, current_user, db)
    items = db.query(ExpenseReportItem).filter_by(report_id=report.report_id).all()
    detail = ReportDetail.model_validate(report)
    detail.item_count = len(items)
    detail.items = [ReportItemOut.model_validate(i) for i in items]
    return detail


@router.get("/{report_id}/download")
def download_report(
    report_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    report = _owned_report(report_id, current_user, db)
    if not report.file_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report file not found.")

    try:
        path = storage.resolve_for_read(report.file_path, current_user.user_id)
    except storage.UploadRejected:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report file not found.")

    if not path.exists():
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="This report file is no longer on the server.",
        )

    return FileResponse(
        path,
        media_type=XLSX_MIME,
        filename=storage.safe_download_name(f"{report.report_name}.xlsx", "report.xlsx"),
    )


@router.delete("/{report_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_report(
    report_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    report = _owned_report(report_id, current_user, db)
    path = report.file_path
    db.delete(report)  # cascade removes the frozen line items
    db.commit()
    if path:
        storage.delete(path)
    return None
