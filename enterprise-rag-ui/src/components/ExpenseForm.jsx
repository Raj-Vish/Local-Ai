import { useState } from "react";
import { LoaderCircle, X } from "lucide-react";
import { CATEGORIES } from "../api/expenses";
import { todayIso } from "../lib/format";

const BLANK = {
  expense_date: todayIso(),
  category: "Hotel",
  vendor: "",
  amount: "",
  description: "",
  document_id: "",
};

// Used for adding a new expense and for editing an existing one. `initial`
// decides which; the parent owns saving so this component stays presentational.
export default function ExpenseForm({ initial, documents, onSave, onCancel, saving }) {
  const [form, setForm] = useState(() => ({ ...BLANK, ...(initial ?? {}) }));
  const [problem, setProblem] = useState(null);

  const set = (key) => (e) => {
    setForm((prev) => ({ ...prev, [key]: e.target.value }));
    if (problem) setProblem(null);
  };

  const submit = (e) => {
    e.preventDefault();
    if (saving) return;

    if (!form.vendor.trim()) return setProblem("Enter who you paid.");
    // Checked as text rather than with a number input: browsers treat
    // decimals and separators differently by locale. The server validates
    // this again regardless -- the screen is never the authority.
    if (!/^\d+(\.\d{1,2})?$/.test(form.amount.trim()))
      return setProblem("Enter an amount like 1250 or 1250.50.");
    if (Number(form.amount) <= 0) return setProblem("Amount must be more than zero.");
    if (form.expense_date > todayIso()) return setProblem("The date cannot be in the future.");

    onSave({
      expense_date: form.expense_date,
      category: form.category,
      vendor: form.vendor.trim(),
      amount: form.amount.trim(),
      description: form.description.trim() || null,
      document_id: form.document_id ? Number(form.document_id) : null,
    });
  };

  return (
    <form className="expense-form" onSubmit={submit}>
      <div className="form-grid">
        <label className="field-label">
          Date
          <input type="date" value={form.expense_date} max={todayIso()}
                 onChange={set("expense_date")} disabled={saving} required />
        </label>

        <label className="field-label">
          Category
          <select value={form.category} onChange={set("category")} disabled={saving}>
            {CATEGORIES.map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
        </label>

        <label className="field-label wide">
          Paid to
          <input type="text" value={form.vendor} placeholder="ABC Hotel"
                 onChange={set("vendor")} disabled={saving} maxLength={180} />
        </label>

        <label className="field-label">
          Amount (₹)
          <input type="text" inputMode="decimal" value={form.amount} placeholder="5000.00"
                 onChange={set("amount")} disabled={saving} />
        </label>

        <label className="field-label wide">
          Note <span className="optional">optional</span>
          <input type="text" value={form.description ?? ""} placeholder="Client visit, Mumbai"
                 onChange={set("description")} disabled={saving} maxLength={2000} />
        </label>

        <label className="field-label">
          Receipt <span className="optional">optional</span>
          <select value={form.document_id ?? ""} onChange={set("document_id")} disabled={saving}>
            <option value="">No document</option>
            {documents.map((d) => (
              <option key={d.document_id} value={d.document_id}>{d.original_filename}</option>
            ))}
          </select>
        </label>
      </div>

      {problem && <p className="form-problem">{problem}</p>}

      <div className="form-actions">
        <button type="button" className="btn-secondary" onClick={onCancel} disabled={saving}>
          <X size={14} /> Cancel
        </button>
        <button type="submit" className="btn-primary compact" disabled={saving}>
          {saving ? <><LoaderCircle size={14} className="spin" /> Saving…</> : "Save expense"}
        </button>
      </div>
    </form>
  );
}
