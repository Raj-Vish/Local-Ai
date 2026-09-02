"""Expense records: the money itself.

Every total returned here is computed in the database or in Python Decimal.
Nothing asks the browser what a sum is, and nothing asks a language model.
"""
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from core.deps import get_current_user
from database import get_db
from models import Document, Expense, ExpenseCategory, User
from schemas import (
    CategoryTotal, ExpenseCreate, ExpenseList, ExpenseOut, ExpenseSummary, ExpenseUpdate,
)

router = APIRouter(prefix="/expenses", tags=["expenses"])

ZERO = Decimal("0.00")


def _owned_expense(expense_id: int, user: User, db: Session) -> Expense:
    expense = db.get(Expense, expense_id)
    if expense is None or expense.user_id != user.user_id:
        # 404 rather than 403: "forbidden" would confirm the row exists.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Expense not found.")
    return expense


def _check_document(document_id: int | None, user: User, db: Session) -> None:
    """A linked document must exist and belong to the same person.

    Without this check, an expense could be attached to someone else's file,
    and the document name would then leak into this user's expense list.
    """
    if document_id is None:
        return
    document = db.get(Document, document_id)
    if document is None or document.user_id != user.user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")


def _filtered(user: User, date_from: date | None, date_to: date | None, category: str | None):
    conditions = [Expense.user_id == user.user_id]
    if date_from is not None:
        conditions.append(Expense.expense_date >= date_from)
    if date_to is not None:
        conditions.append(Expense.expense_date <= date_to)
    if category is not None:
        conditions.append(Expense.category == category)
    return conditions


@router.post("", response_model=ExpenseOut, status_code=status.HTTP_201_CREATED)
def create_expense(
    payload: ExpenseCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _check_document(payload.document_id, current_user, db)

    expense = Expense(
        user_id=current_user.user_id,
        document_id=payload.document_id,
        expense_date=payload.expense_date,
        category=payload.category.value,
        vendor=payload.vendor,
        description=payload.description,
        amount=payload.amount,
        currency=payload.currency,
        # A person typed this, so there is nothing to confirm. Extracted rows
        # will arrive as False and wait for a human.
        is_verified=True,
        extraction_confidence=Decimal("1.00"),
    )
    db.add(expense)
    db.commit()
    db.refresh(expense)
    return expense


@router.get("", response_model=ExpenseList)
def list_expenses(
    date_from: date | None = Query(None, alias="from"),
    date_to: date | None = Query(None, alias="to"),
    category: ExpenseCategory | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conditions = _filtered(current_user, date_from, date_to, category.value if category else None)

    rows = db.execute(
        select(Expense)
        .where(*conditions)
        .order_by(Expense.expense_date.desc(), Expense.expense_id.desc())
    ).scalars().all()

    # Summed in SQL over the same conditions, not by adding up the rows above:
    # the total stays correct if the list is ever paginated.
    total = db.execute(select(func.coalesce(func.sum(Expense.amount), ZERO)).where(*conditions)).scalar()

    return ExpenseList(
        items=[ExpenseOut.model_validate(r) for r in rows],
        count=len(rows),
        total=total,
    )


@router.get("/summary", response_model=ExpenseSummary)
def summary(
    date_from: date | None = Query(None, alias="from"),
    date_to: date | None = Query(None, alias="to"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Totals for the whole period and per category, computed by the database."""
    conditions = _filtered(current_user, date_from, date_to, None)

    grouped = db.execute(
        select(
            Expense.category,
            func.coalesce(func.sum(Expense.amount), ZERO),
            func.count(Expense.expense_id),
        )
        .where(*conditions)
        .group_by(Expense.category)
        .order_by(func.sum(Expense.amount).desc())
    ).all()

    total = sum((row[1] for row in grouped), ZERO)
    count = sum(row[2] for row in grouped)

    return ExpenseSummary(
        total=total,
        count=count,
        # Only INR is supported for now. Summing across currencies needs
        # exchange rates as of each transaction date, which is its own project.
        currency="INR",
        by_category=[
            CategoryTotal(category=c, total=t, count=n) for c, t, n in grouped
        ],
        period_start=date_from,
        period_end=date_to,
    )


@router.get("/{expense_id}", response_model=ExpenseOut)
def get_expense(
    expense_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _owned_expense(expense_id, current_user, db)


@router.patch("/{expense_id}", response_model=ExpenseOut)
def update_expense(
    expense_id: int,
    payload: ExpenseUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    expense = _owned_expense(expense_id, current_user, db)
    # exclude_unset so an omitted field keeps its value, while a field
    # explicitly sent as null still clears it.
    changes = payload.model_dump(exclude_unset=True)

    if "document_id" in changes:
        _check_document(changes["document_id"], current_user, db)
    if "category" in changes and changes["category"] is not None:
        changes["category"] = changes["category"].value

    for field, value in changes.items():
        setattr(expense, field, value)

    db.commit()
    db.refresh(expense)
    return expense


@router.delete("/{expense_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_expense(
    expense_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    expense = _owned_expense(expense_id, current_user, db)
    db.delete(expense)
    db.commit()
    return None
