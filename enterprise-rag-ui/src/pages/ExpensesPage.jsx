import { useState, useEffect, useCallback } from "react";
import {
  Plus, Pencil, Trash2, LoaderCircle, AlertCircle, PanelLeftOpen,
  RefreshCw, Paperclip, Wallet
} from "lucide-react";
import {
  listExpenses, getSummary, createExpense, updateExpense, deleteExpense, CATEGORIES,
} from "../api/expenses";
import { listDocuments } from "../api/documents";
import { ApiError } from "../api/client";
import { formatMoney, formatDate, monthRange, currentMonth } from "../lib/format";
import ExpenseForm from "../components/ExpenseForm";
import "../styles/documents.css";
import "../styles/expenses.css";

export default function ExpensesPage({ isSidebarOpen, onOpenSidebar }) {
  const [month, setMonth] = useState(currentMonth);
  const [category, setCategory] = useState("");
  const [expenses, setExpenses] = useState([]);
  // Held separately from the list because it is the server's figure, not
  // something derived from the rows on screen.
  const [summary, setSummary] = useState(null);
  const [documents, setDocuments] = useState([]);
  const [loadState, setLoadState] = useState("loading");
  const [error, setError] = useState(null);
  const [adding, setAdding] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [savingId, setSavingId] = useState(null);
  const [confirmId, setConfirmId] = useState(null);

  const filters = { ...monthRange(month), category: category || undefined };

  const load = useCallback(async (signal) => {
    try {
      const [list, sum] = await Promise.all([
        listExpenses(filters, signal),
        getSummary(monthRange(month), signal),
      ]);
      setExpenses(list.items);
      setSummary({ ...sum, filteredTotal: list.total, filteredCount: list.count });
      setLoadState("ready");
      setError(null);
    } catch (err) {
      if (err.name === "AbortError") return;
      setLoadState("error");
      setError(err instanceof ApiError ? err.message : "Could not load your expenses.");
    }
    // filters is rebuilt every render; month and category are what actually change.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [month, category]);

  useEffect(() => {
    const controller = new AbortController();
    void (async () => { await load(controller.signal); })();
    return () => controller.abort();
  }, [load]);

  // Only needed to populate the receipt dropdown, so a failure here must not
  // stop the expense list from working.
  useEffect(() => {
    const controller = new AbortController();
    void (async () => {
      try {
        const data = await listDocuments(controller.signal);
        setDocuments(data.items);
      } catch { /* the dropdown simply stays empty */ }
    })();
    return () => controller.abort();
  }, []);

  const handleCreate = async (body) => {
    setSavingId("new");
    setError(null);
    try {
      await createExpense(body);
      setAdding(false);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not save that expense.");
    } finally {
      setSavingId(null);
    }
  };

  const handleUpdate = async (id, body) => {
    setSavingId(id);
    setError(null);
    try {
      await updateExpense(id, body);
      setEditingId(null);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not update that expense.");
    } finally {
      setSavingId(null);
    }
  };

  const handleDelete = async (expense) => {
    if (confirmId !== expense.expense_id) {
      setConfirmId(expense.expense_id);
      return;
    }
    setSavingId(expense.expense_id);
    setError(null);
    try {
      await deleteExpense(expense.expense_id);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not delete that expense.");
    } finally {
      setSavingId(null);
      setConfirmId(null);
    }
  };

  const documentName = (id) =>
    documents.find((d) => d.document_id === id)?.original_filename;

  return (
    <main className="page">
      <header className="page-header">
        {!isSidebarOpen && (
          <button className="icon-btn" onClick={onOpenSidebar} title="Open sidebar" aria-label="Open sidebar">
            <PanelLeftOpen size={18} />
          </button>
        )}
        <div className="page-title">
          <h1>Expenses</h1>
          <p>What you have spent, and what it adds up to.</p>
        </div>
        <button className="icon-btn" onClick={() => load()} title="Refresh" aria-label="Refresh">
          <RefreshCw size={16} />
        </button>
      </header>

      <div className="page-body">
        <div className="filter-bar">
          <label className="filter">
            <span>Month</span>
            <input type="month" value={month} onChange={(e) => setMonth(e.target.value)} />
          </label>
          <label className="filter">
            <span>Category</span>
            <select value={category} onChange={(e) => setCategory(e.target.value)}>
              <option value="">All categories</option>
              {CATEGORIES.map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
          </label>
          <button
            className="btn-primary compact push-right"
            onClick={() => { setAdding(true); setEditingId(null); }}
            disabled={adding}
          >
            <Plus size={15} /> Add expense
          </button>
        </div>

        {summary && (
          <div className="summary-card">
            <div className="summary-main">
              <span className="summary-label">
                {category ? `${category} in ` : "Total for "}
                {new Date(`${month}-01`).toLocaleDateString(undefined, { month: "long", year: "numeric" })}
              </span>
              {/* Straight from the server. Nothing on this page adds anything up. */}
              <span className="summary-total">{formatMoney(summary.filteredTotal)}</span>
              <span className="summary-count">
                {summary.filteredCount} {summary.filteredCount === 1 ? "expense" : "expenses"}
              </span>
            </div>
            {summary.by_category.length > 0 && (
              <div className="summary-chips">
                {summary.by_category.map((c) => (
                  <button
                    key={c.category}
                    className={`chip ${category === c.category ? "active" : ""}`}
                    onClick={() => setCategory(category === c.category ? "" : c.category)}
                    title={`Show only ${c.category}`}
                  >
                    {c.category} <strong>{formatMoney(c.total)}</strong>
                  </button>
                ))}
              </div>
            )}
          </div>
        )}

        {adding && (
          <ExpenseForm
            documents={documents}
            saving={savingId === "new"}
            onSave={handleCreate}
            onCancel={() => setAdding(false)}
          />
        )}

        {error && (
          <div className="page-error" role="alert">
            <AlertCircle size={15} /><span>{error}</span>
          </div>
        )}

        {loadState === "loading" && (
          <div className="page-placeholder">
            <LoaderCircle size={20} className="spin" /><span>Loading your expenses…</span>
          </div>
        )}

        {loadState === "error" && (
          <div className="page-placeholder">
            <span>Could not reach the server.</span>
            <button className="btn-secondary" onClick={() => load()}>Try again</button>
          </div>
        )}

        {loadState === "ready" && expenses.length === 0 && !adding && (
          <div className="page-placeholder">
            <Wallet size={22} />
            <span>No expenses recorded for this period.</span>
            <span className="muted">Add one to get started.</span>
          </div>
        )}

        {loadState === "ready" && expenses.length > 0 && (
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Date</th><th>Category</th><th>Paid to</th>
                  <th className="num">Amount</th><th><span className="sr-only">Actions</span></th>
                </tr>
              </thead>
              <tbody>
                {expenses.map((expense) =>
                  editingId === expense.expense_id ? (
                    <tr key={expense.expense_id} className="editing">
                      <td colSpan={5}>
                        <ExpenseForm
                          initial={{
                            expense_date: expense.expense_date,
                            category: expense.category,
                            vendor: expense.vendor,
                            amount: String(expense.amount),
                            description: expense.description ?? "",
                            document_id: expense.document_id ?? "",
                          }}
                          documents={documents}
                          saving={savingId === expense.expense_id}
                          onSave={(body) => handleUpdate(expense.expense_id, body)}
                          onCancel={() => setEditingId(null)}
                        />
                      </td>
                    </tr>
                  ) : (
                    <tr key={expense.expense_id} className={confirmId === expense.expense_id ? "confirming" : ""}>
                      <td className="nowrap">{formatDate(expense.expense_date)}</td>
                      <td><span className="pill">{expense.category}</span></td>
                      <td>
                        <span className="cell-name">
                          <span title={expense.vendor}>{expense.vendor}</span>
                          {expense.document_id && (
                            <Paperclip size={12} className="muted-icon"
                                       title={documentName(expense.document_id) ?? "Receipt attached"} />
                          )}
                        </span>
                        {expense.description && <span className="cell-note">{expense.description}</span>}
                      </td>
                      <td className="num money">{formatMoney(expense.amount, expense.currency)}</td>
                      <td className="actions">
                        <button className="icon-btn"
                                onClick={() => { setEditingId(expense.expense_id); setAdding(false); }}
                                disabled={savingId === expense.expense_id}
                                title="Edit" aria-label={`Edit ${expense.vendor}`}>
                          <Pencil size={15} />
                        </button>
                        <button className={`icon-btn danger ${confirmId === expense.expense_id ? "armed" : ""}`}
                                onClick={() => handleDelete(expense)}
                                onBlur={() => confirmId === expense.expense_id && setConfirmId(null)}
                                disabled={savingId === expense.expense_id}
                                title={confirmId === expense.expense_id ? "Click again to confirm" : "Delete"}
                                aria-label={confirmId === expense.expense_id
                                  ? `Confirm deleting ${expense.vendor}` : `Delete ${expense.vendor}`}>
                          {savingId === expense.expense_id
                            ? <LoaderCircle size={15} className="spin" />
                            : <Trash2 size={15} />}
                        </button>
                      </td>
                    </tr>
                  )
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </main>
  );
}
