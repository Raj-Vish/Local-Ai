"""Stage 6: semantic search over your own documents.

What this is for, and what it is not for
----------------------------------------
This finds documents by meaning: "Mumbai hotel receipt" will find a bill that
says "TAJ RESIDENCY / Colaba, Mumbai" without those words appearing together.

It is NOT how a financial total is answered. "How much did I spend on hotels"
is a question for MySQL -- SELECT SUM(amount) over verified expenses, which
/expenses/summary already does exactly. Retrieval finds documents; the
database does arithmetic. When the language model is connected it will phrase
figures that MySQL produced, and will never produce one itself.

Isolation
---------
Every route here takes the user from get_current_user and passes that user_id
to the vector store, which filters on it. A caller cannot name a user, a
document or a collection, so there is no request that reaches another
person's chunks.
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from config import settings
from core.deps import get_current_user
from database import get_db
from models import Document, DocumentIndex, Expense, IndexStatus, User
from schemas import (
    AskAnswer, AskQuery, IndexStatusOut, SearchHit, SearchQuery, SearchResults,
)
from services import embeddings, llm, vector_store

log = logging.getLogger("uvicorn.error")

router = APIRouter(prefix="/rag", tags=["rag"])


@router.post("/search", response_model=SearchResults)
def search(
    payload: SearchQuery,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Find this user's document chunks that mean something like the query."""
    top_k = payload.top_k or settings.RAG_TOP_K
    top_k = max(1, min(top_k, settings.RAG_MAX_TOP_K))

    # Nothing indexed is a different answer from nothing matching, and saying
    # "no results" for an empty index sends people looking for the wrong bug.
    try:
        indexed_chunks = vector_store.count_for_user(current_user.user_id)
    except vector_store.VectorStoreError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))

    if indexed_chunks == 0:
        return SearchResults(query=payload.query, count=0, top_k=top_k,
                             results=[], index_empty=True)

    try:
        query_vector = embeddings.embed_query(payload.query)
    except embeddings.EmbeddingError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))

    try:
        # user_id is the server's, never the caller's.
        hits = vector_store.search(
            user_id=current_user.user_id, query_vector=query_vector, top_k=top_k
        )
    except vector_store.VectorStoreError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))

    # A vector can outlive its document if a delete half-failed. Confirm every
    # hit against a document this user still owns before returning it.
    owned = {
        row[0] for row in db.execute(
            select(Document.document_id).where(Document.user_id == current_user.user_id)
        ).all()
    }
    safe = [h for h in hits if h["document_id"] in owned]
    if len(safe) != len(hits):
        log.warning("rag: dropped %d hit(s) with no owned document for user %s",
                    len(hits) - len(safe), current_user.user_id)

    return SearchResults(
        query=payload.query,
        count=len(safe),
        top_k=top_k,
        results=[SearchHit(**h) for h in safe],
    )


@router.get("/status", response_model=IndexStatusOut)
def index_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """What this user has searchable. Scoped like everything else."""
    total = db.execute(
        select(func.count(Document.document_id)).where(Document.user_id == current_user.user_id)
    ).scalar() or 0

    rows = db.execute(
        select(DocumentIndex.status, func.count(DocumentIndex.document_id))
        .where(DocumentIndex.user_id == current_user.user_id)
        .group_by(DocumentIndex.status)
    ).all()
    by_status = {status_value: count for status_value, count in rows}

    indexed = by_status.get(IndexStatus.INDEXED.value, 0)
    failed = by_status.get(IndexStatus.FAILED.value, 0)

    try:
        chunks = vector_store.count_for_user(current_user.user_id)
        reachable = True
    except vector_store.VectorStoreError:
        chunks, reachable = 0, False

    return IndexStatusOut(
        documents_total=total,
        documents_indexed=indexed,
        documents_failed=failed,
        # Ready but never indexed, plus anything still marked pending.
        documents_pending=max(0, total - indexed - failed),
        chunks_indexed=chunks,
        embed_model=settings.EMBED_MODEL,
        search_available=reachable and embeddings.available(),
    )


def _money_facts(db: Session, user: User) -> list[str]:
    """Figures for the model to quote, computed by the database.

    This is the "MySQL calculates, the model only phrases" rule made
    concrete. Rather than hoping a language model adds up the amounts in some
    retrieved text, the totals are computed in SQL over verified expenses and
    handed over as facts it must copy.
    """
    facts: list[str] = []

    total, count = db.execute(
        select(func.coalesce(func.sum(Expense.amount), 0), func.count(Expense.expense_id))
        .where(Expense.user_id == user.user_id, Expense.is_verified.is_(True))
    ).one()
    if count:
        facts.append(f"Total verified expenses: INR {total} across {count} expense(s).")

    per_category = db.execute(
        select(Expense.category, func.coalesce(func.sum(Expense.amount), 0),
               func.count(Expense.expense_id))
        .where(Expense.user_id == user.user_id, Expense.is_verified.is_(True))
        .group_by(Expense.category)
        .order_by(func.sum(Expense.amount).desc())
    ).all()
    for category, amount, how_many in per_category:
        facts.append(f"{category}: INR {amount} across {how_many} expense(s).")

    return facts


@router.post("/ask", response_model=AskAnswer)
def ask(
    payload: AskQuery,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Answer a question from this user's documents and their own figures.

    Three steps, in this order and for this reason:

      1. MySQL computes the money. Always, and regardless of the question.
      2. Retrieval finds relevant extracts from this user's documents.
      3. The language service phrases an answer from 1 and 2.

    Step 3 is the only optional one. If no language service is configured --
    which is the normal state on this machine, since the model runs on a
    teammate's -- the facts and sources are still returned, and the response
    says plainly why there is no phrased answer. Retrieval does not depend on
    the model being there.
    """
    results = search(SearchQuery(query=payload.question, top_k=payload.top_k),
                     current_user=current_user, db=db)
    facts = _money_facts(db, current_user)

    reachable, why = llm.available()
    if not reachable:
        return AskAnswer(
            question=payload.question,
            answer=None,
            answered_by_model=False,
            unavailable_reason=why,
            facts=facts,
            sources=results.results,
        )

    try:
        answer = llm.generate(
            question=payload.question,
            context=[hit.text for hit in results.results],
            facts=facts,
        )
    except llm.LLMUnavailable as exc:
        return AskAnswer(
            question=payload.question,
            answer=None,
            answered_by_model=False,
            unavailable_reason=str(exc),
            facts=facts,
            sources=results.results,
        )

    return AskAnswer(
        question=payload.question,
        answer=answer,
        answered_by_model=True,
        facts=facts,
        sources=results.results,
    )
