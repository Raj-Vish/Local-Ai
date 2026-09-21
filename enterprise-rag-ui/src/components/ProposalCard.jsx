import { useState } from "react";
import { LoaderCircle, X, Check, Quote, AlertTriangle } from "lucide-react";
import { CATEGORIES } from "../api/expenses";
import { todayIso } from "../lib/format";

// "We read this from your receipt." Every field is editable, and every field
// shows the line it came from, so confirming is a check rather than an act of
// faith. Nothing here has been saved: the parent posts to /expenses only when
// Confirm is pressed, which is what makes the resulting expense verified.
//
// A low-confidence field is marked, not hidden. Hiding uncertainty is how a
// wrong figure ends up in an expense claim.
const LOW_CONFIDENCE = 0.7;

function Evidence({ field }) {
  if (!field?.evidence) return null;
  return (
    <span className="proposal-evidence" title={`Line ${field.line_no} of the document`}>
      <Quote size={10} />
      <code>{field.evidence.trim()}</code>
    </span>
  );
}

function Note({ field }) {
  if (!field?.note) return null;
  return (
    <span className="proposal-note">
      <AlertTriangle size={11} />
      {field.note}
    </span>
  );
}

// The receipt is not a choice here: a proposal always belongs to the document
// it was read from, so document_id comes from the proposal itself.
export default function ProposalCard({ proposal, saving, onConfirm, onDiscard }) {
  const [form, setForm] = useState(() => ({
    expense_date: proposal.expense_date.value ?? todayIso(),
    category: proposal.category.value ?? "Other",
    vendor: proposal.vendor.value ?? "",
    amount: proposal.amount.value ?? "",
    description: "",
    document_id: String(proposal.document_id),
  }));
  const [problem, setProblem] = useState(null);

  const set = (key) => (e) => {
    setForm((prev) => ({ ...prev, [key]: e.target.value }));
    if (problem) setProblem(null);
  };

  const submit = (e) => {
    e.preventDefault();
    if (saving) return;
    // The same checks the manual form makes. The server validates again.
    if (!form.vendor.trim()) return setProblem("Enter who you paid.");
    if (!/^\d+(\.\d{1,2})?$/.test(form.amount.trim()))
      return setProblem("Enter an amount like 1250 or 1250.50.");
    if (Number(form.amount) <= 0) return setProblem("Amount must be more than zero.");
    if (form.expense_date > todayIso()) return setProblem("The date cannot be in the future.");

    onConfirm({
      expense_date: form.expense_date,
      category: form.category,
      vendor: form.vendor.trim(),
      amount: form.amount.trim(),
      description: form.description.trim() || null,
      document_id: Number(form.document_id),
    });
  };

  const uncertain = (name) => {
    const f = proposal[name];
    return !f?.value || f.confidence < LOW_CONFIDENCE;
  };

  return (
    <form className="expense-form proposal-card" onSubmit={submit}>
      <div className="proposal-head">
        <strong>We read this from {proposal.original_filename}</strong>
        <span className="proposal-sub">
          Check each field against the receipt. Nothing is saved until you confirm.
        </span>
      </div>

      {proposal.unresolved.length > 0 && (
        <p className="proposal-missing">
          <AlertTriangle size={13} />
          Could not read: {proposal.unresolved.map((f) => f.replace("expense_", "")).join(", ")}.
          Please fill {proposal.unresolved.length === 1 ? "it" : "them"} in.
        </p>
      )}

      <div className="form-grid">
        <label className={`field-label ${uncertain("expense_date") ? "uncertain" : ""}`}>
          Date
          <input type="date" value={form.expense_date} max={todayIso()}
                 onChange={set("expense_date")} disabled={saving} required />
          <Evidence field={proposal.expense_date} />
          <Note field={proposal.expense_date} />
        </label>

        <label className={`field-label ${uncertain("category") ? "uncertain" : ""}`}>
          Category
          <select value={form.category} onChange={set("category")} disabled={saving}>
            {CATEGORIES.map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
          <Evidence field={proposal.category} />
          <Note field={proposal.category} />
        </label>

        <label className={`field-label wide ${uncertain("vendor") ? "uncertain" : ""}`}>
          Paid to
          <input type="text" value={form.vendor} placeholder="ABC Hotel"
                 onChange={set("vendor")} disabled={saving} maxLength={180} />
          <Evidence field={proposal.vendor} />
          <Note field={proposal.vendor} />
        </label>

        <label className={`field-label ${uncertain("amount") ? "uncertain" : ""}`}>
          Amount (₹)
          <input type="text" inputMode="decimal" value={form.amount} placeholder="5000.00"
                 onChange={set("amount")} disabled={saving} />
          <Evidence field={proposal.amount} />
          <Note field={proposal.amount} />
        </label>

        <label className="field-label wide">
          Note <span className="optional">optional</span>
          <input type="text" value={form.description} placeholder="Client visit, Mumbai"
                 onChange={set("description")} disabled={saving} maxLength={2000} />
        </label>
      </div>

      {problem && <p className="form-problem">{problem}</p>}

      <div className="form-actions">
        <button type="button" className="btn-secondary" onClick={onDiscard} disabled={saving}>
          <X size={14} /> Discard
        </button>
        <button type="submit" className="btn-primary compact" disabled={saving}>
          {saving
            ? <><LoaderCircle size={14} className="spin" /> Saving…</>
            : <><Check size={14} /> Confirm expense</>}
        </button>
      </div>
    </form>
  );
}
