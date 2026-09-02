import { useState, useEffect, useCallback } from "react";
import {
  FileSpreadsheet, Download, Trash2, LoaderCircle, AlertCircle,
  PanelLeftOpen, RefreshCw, Plus, X
} from "lucide-react";
import { listReports, generateReport, deleteReport, downloadReport } from "../api/reports";
import { ApiError } from "../api/client";
import { formatMoney, formatDate, monthRange, currentMonth, todayIso } from "../lib/format";
import "../styles/documents.css";
import "../styles/expenses.css";

export default function ReportsPage({ isSidebarOpen, onOpenSidebar }) {
  const [reports, setReports] = useState([]);
  const [loadState, setLoadState] = useState("loading");
  const [error, setError] = useState(null);
  const [creating, setCreating] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [busyId, setBusyId] = useState(null);
  const [confirmId, setConfirmId] = useState(null);

  const thisMonth = monthRange(currentMonth());
  const [form, setForm] = useState({
    report_name: "",
    period_start: thisMonth.from,
    period_end: thisMonth.to,
  });

  const load = useCallback(async (signal) => {
    try {
      const data = await listReports(signal);
      setReports(data.items);
      setLoadState("ready");
      setError(null);
    } catch (err) {
      if (err.name === "AbortError") return;
      setLoadState("error");
      setError(err instanceof ApiError ? err.message : "Could not load your reports.");
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    void (async () => { await load(controller.signal); })();
    return () => controller.abort();
  }, [load]);

  const handleGenerate = async (e) => {
    e.preventDefault();
    if (generating) return;
    if (!form.report_name.trim()) return setError("Give the report a name.");
    if (form.period_end < form.period_start) return setError("The end date is before the start date.");

    setGenerating(true);
    setError(null);
    try {
      await generateReport({ ...form, report_name: form.report_name.trim() });
      setCreating(false);
      setForm((prev) => ({ ...prev, report_name: "" }));
      await load();
    } catch (err) {
      // A period with nothing in it is the common case here, and the server's
      // own wording explains it better than anything generic would.
      setError(err instanceof ApiError ? err.message : "Could not generate that report.");
    } finally {
      setGenerating(false);
    }
  };

  const handleDownload = async (report) => {
    setBusyId(report.report_id);
    setError(null);
    try {
      await downloadReport(report.report_id, report.report_name);
    } catch {
      setError("Could not download that report.");
    } finally {
      setBusyId(null);
    }
  };

  const handleDelete = async (report) => {
    if (confirmId !== report.report_id) {
      setConfirmId(report.report_id);
      return;
    }
    setBusyId(report.report_id);
    setError(null);
    try {
      await deleteReport(report.report_id);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not delete that report.");
    } finally {
      setBusyId(null);
      setConfirmId(null);
    }
  };

  const set = (key) => (e) => {
    setForm((prev) => ({ ...prev, [key]: e.target.value }));
    if (error) setError(null);
  };

  return (
    <main className="page">
      <header className="page-header">
        {!isSidebarOpen && (
          <button className="icon-btn" onClick={onOpenSidebar} title="Open sidebar" aria-label="Open sidebar">
            <PanelLeftOpen size={18} />
          </button>
        )}
        <div className="page-title">
          <h1>Reports</h1>
          <p>Generate an expense report and download it as a spreadsheet.</p>
        </div>
        <button className="icon-btn" onClick={() => load()} title="Refresh" aria-label="Refresh">
          <RefreshCw size={16} />
        </button>
      </header>

      <div className="page-body">
        {!creating && (
          <div className="filter-bar">
            <button className="btn-primary compact push-right" onClick={() => setCreating(true)}>
              <Plus size={15} /> New report
            </button>
          </div>
        )}

        {creating && (
          <form className="expense-form" onSubmit={handleGenerate}>
            <div className="form-grid">
              <label className="field-label wide">
                Report name
                <input type="text" value={form.report_name} placeholder="September client visit"
                       onChange={set("report_name")} disabled={generating} maxLength={180} autoFocus />
              </label>
              <label className="field-label">
                From
                <input type="date" value={form.period_start} max={todayIso()}
                       onChange={set("period_start")} disabled={generating} required />
              </label>
              <label className="field-label">
                To
                <input type="date" value={form.period_end} max={todayIso()}
                       onChange={set("period_end")} disabled={generating} required />
              </label>
            </div>
            <p className="form-hint">
              Only confirmed expenses in this period are included.
            </p>
            <div className="form-actions">
              <button type="button" className="btn-secondary" onClick={() => setCreating(false)} disabled={generating}>
                <X size={14} /> Cancel
              </button>
              <button type="submit" className="btn-primary compact" disabled={generating}>
                {generating
                  ? <><LoaderCircle size={14} className="spin" /> Generating…</>
                  : "Generate report"}
              </button>
            </div>
          </form>
        )}

        {error && (
          <div className="page-error" role="alert">
            <AlertCircle size={15} /><span>{error}</span>
          </div>
        )}

        {loadState === "loading" && (
          <div className="page-placeholder">
            <LoaderCircle size={20} className="spin" /><span>Loading your reports…</span>
          </div>
        )}

        {loadState === "error" && (
          <div className="page-placeholder">
            <span>Could not reach the server.</span>
            <button className="btn-secondary" onClick={() => load()}>Try again</button>
          </div>
        )}

        {loadState === "ready" && reports.length === 0 && !creating && (
          <div className="page-placeholder">
            <FileSpreadsheet size={22} />
            <span>No reports yet.</span>
            <span className="muted">Generate one from your recorded expenses.</span>
          </div>
        )}

        {loadState === "ready" && reports.length > 0 && (
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Report</th><th>Period</th><th className="num">Items</th>
                  <th className="num">Total</th><th><span className="sr-only">Actions</span></th>
                </tr>
              </thead>
              <tbody>
                {reports.map((report) => (
                  <tr key={report.report_id} className={confirmId === report.report_id ? "confirming" : ""}>
                    <td>
                      <span className="cell-name">
                        <FileSpreadsheet size={14} />
                        <span title={report.report_name}>{report.report_name}</span>
                      </span>
                      {report.generated_at && (
                        <span className="cell-note">Generated {formatDate(report.generated_at)}</span>
                      )}
                    </td>
                    <td className="nowrap">
                      {formatDate(report.period_start)} – {formatDate(report.period_end)}
                    </td>
                    <td className="num">{report.item_count}</td>
                    <td className="num money">{formatMoney(report.total_amount, report.currency)}</td>
                    <td className="actions">
                      <button className="icon-btn" onClick={() => handleDownload(report)}
                              disabled={busyId === report.report_id}
                              title="Download spreadsheet" aria-label={`Download ${report.report_name}`}>
                        {busyId === report.report_id
                          ? <LoaderCircle size={15} className="spin" />
                          : <Download size={15} />}
                      </button>
                      <button className={`icon-btn danger ${confirmId === report.report_id ? "armed" : ""}`}
                              onClick={() => handleDelete(report)}
                              onBlur={() => confirmId === report.report_id && setConfirmId(null)}
                              disabled={busyId === report.report_id}
                              title={confirmId === report.report_id ? "Click again to confirm" : "Delete"}
                              aria-label={confirmId === report.report_id
                                ? `Confirm deleting ${report.report_name}` : `Delete ${report.report_name}`}>
                        <Trash2 size={15} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </main>
  );
}
