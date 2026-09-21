import { useState, useEffect, useRef, useCallback, Fragment } from "react";
import {
  Upload, FileText, Image as ImageIcon, Download, Trash2,
  LoaderCircle, AlertCircle, PanelLeftOpen, RefreshCw,
  ScanText, ChevronDown, ChevronRight, RotateCw, Check, Clock, Sparkles
} from "lucide-react";
import {
  listDocuments, uploadDocument, deleteDocument, downloadDocument,
  getDocumentText, retryExtraction, proposeExpense,
} from "../api/documents";
import { createExpense } from "../api/expenses";
import ProposalCard from "../components/ProposalCard";
import { ApiError } from "../api/client";
import { formatBytes, formatDate, fileKind } from "../lib/format";
import "../styles/documents.css";

const ACCEPT = ".pdf,.jpg,.jpeg,.png";

// How the server's extraction status reads on screen. "uploaded" means the
// background task has not picked it up yet, which from here is still waiting.
const STATUS = {
  uploaded:   { label: "Queued",     Icon: Clock,         tone: "wait" },
  processing: { label: "Reading…",   Icon: LoaderCircle,  tone: "wait", spin: true },
  ready:      { label: "Text ready", Icon: Check,         tone: "ok" },
  failed:     { label: "Unreadable", Icon: AlertCircle,   tone: "bad" },
};

// While anything is still being read, poll so the row updates on its own.
const POLL_MS = 2500;
const isPending = (d) => d.status === "uploaded" || d.status === "processing";

export default function DocumentsPage({ isSidebarOpen, onOpenSidebar }) {
  const [documents, setDocuments] = useState([]);
  const [loadState, setLoadState] = useState("loading"); // loading | ready | error
  const [error, setError] = useState(null);
  const [uploading, setUploading] = useState([]);   // filenames in flight
  const [confirmId, setConfirmId] = useState(null); // delete armed for this id
  const [busyId, setBusyId] = useState(null);
  const [isDragging, setIsDragging] = useState(false);
  const [openTextId, setOpenTextId] = useState(null);   // row whose text is shown
  const [textCache, setTextCache] = useState({});       // documentId -> payload
  const [textLoadingId, setTextLoadingId] = useState(null);
  const [proposal, setProposal] = useState(null);        // the open suggestion
  const [proposingId, setProposingId] = useState(null);
  const [savingExpense, setSavingExpense] = useState(false);
  const [confirmedNote, setConfirmedNote] = useState(null);

  const fileInputRef = useRef(null);
  // Drag events fire for every child element; counting enter/leave avoids the
  // highlight flickering as the pointer crosses them.
  const dragDepth = useRef(0);

  const refresh = useCallback(async (signal) => {
    try {
      const data = await listDocuments(signal);
      setDocuments(data.items);
      setLoadState("ready");
    } catch (err) {
      if (err.name === "AbortError") return;
      setLoadState("error");
      setError(err instanceof ApiError ? err.message : "Could not load your documents.");
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    // Wrapped so the first state change provably happens after an await,
    // never synchronously during the effect.
    void (async () => { await refresh(controller.signal); })();
    return () => controller.abort();
  }, [refresh]);

  // Extraction runs in the background on the server, so the row that says
  // "Reading…" has to find out on its own when it is done.
  useEffect(() => {
    if (!documents.some(isPending)) return;
    const controller = new AbortController();
    const timer = setTimeout(() => { void refresh(controller.signal); }, POLL_MS);
    return () => { clearTimeout(timer); controller.abort(); };
  }, [documents, refresh]);

  const handleShowText = async (doc) => {
    if (openTextId === doc.document_id) {
      setOpenTextId(null);
      return;
    }
    setOpenTextId(doc.document_id);
    if (textCache[doc.document_id]) return;
    setTextLoadingId(doc.document_id);
    try {
      const data = await getDocumentText(doc.document_id);
      setTextCache((prev) => ({ ...prev, [doc.document_id]: data }));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not load the extracted text.");
      setOpenTextId(null);
    } finally {
      setTextLoadingId(null);
    }
  };

  const handleRetry = async (doc) => {
    setBusyId(doc.document_id);
    setError(null);
    try {
      await retryExtraction(doc.document_id);
      // Drop the cached text so the next open shows the new result.
      setTextCache((prev) => {
        const next = { ...prev };
        delete next[doc.document_id];
        return next;
      });
      await refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not re-read that document.");
    } finally {
      setBusyId(null);
    }
  };

  const handlePropose = async (doc) => {
    setProposingId(doc.document_id);
    setError(null);
    setConfirmedNote(null);
    try {
      // Read-only: this returns a suggestion and stores nothing.
      const data = await proposeExpense(doc.document_id);
      setProposal(data);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not read fields from that document.");
    } finally {
      setProposingId(null);
    }
  };

  // The proposal becomes an expense only here, through the ordinary create
  // endpoint -- so it lands verified because a person agreed to it.
  const handleConfirmProposal = async (body) => {
    setSavingExpense(true);
    setError(null);
    try {
      const created = await createExpense(body);
      setConfirmedNote(
        `Saved ${created.vendor} — ₹${created.amount} on ${created.expense_date}. It is on the Expenses page.`
      );
      setProposal(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not save that expense.");
    } finally {
      setSavingExpense(false);
    }
  };

  const handleFiles = async (fileList) => {
    const files = Array.from(fileList ?? []);
    if (!files.length) return;
    setError(null);
    setUploading((prev) => [...prev, ...files.map((f) => f.name)]);

    // Sequential rather than parallel: the server writes to one disk, and a
    // failure part-way is easier to report when uploads are ordered.
    for (const file of files) {
      try {
        const created = await uploadDocument(file);
        setDocuments((prev) => [created, ...prev]);
      } catch (err) {
        setError(
          err instanceof ApiError
            ? `${file.name}: ${err.message}`
            : `${file.name}: upload failed.`
        );
      } finally {
        setUploading((prev) => {
          const next = [...prev];
          const at = next.indexOf(file.name);
          if (at !== -1) next.splice(at, 1);
          return next;
        });
      }
    }
  };

  const handleDelete = async (doc) => {
    if (confirmId !== doc.document_id) {
      setConfirmId(doc.document_id);
      return;
    }
    setBusyId(doc.document_id);
    setError(null);
    try {
      await deleteDocument(doc.document_id);
      setDocuments((prev) => prev.filter((d) => d.document_id !== doc.document_id));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not delete that document.");
    } finally {
      setBusyId(null);
      setConfirmId(null);
    }
  };

  const handleDownload = async (doc) => {
    setBusyId(doc.document_id);
    setError(null);
    try {
      await downloadDocument(doc.document_id, doc.original_filename);
    } catch {
      setError("Could not download that file.");
    } finally {
      setBusyId(null);
    }
  };

  const onDrop = (e) => {
    e.preventDefault();
    dragDepth.current = 0;
    setIsDragging(false);
    handleFiles(e.dataTransfer.files);
  };

  return (
    <main
      className="page"
      onDragEnter={(e) => { e.preventDefault(); dragDepth.current += 1; setIsDragging(true); }}
      onDragOver={(e) => e.preventDefault()}
      onDragLeave={(e) => {
        e.preventDefault();
        dragDepth.current -= 1;
        if (dragDepth.current <= 0) setIsDragging(false);
      }}
      onDrop={onDrop}
    >
      <header className="page-header">
        {!isSidebarOpen && (
          <button className="icon-btn" onClick={onOpenSidebar} title="Open sidebar" aria-label="Open sidebar">
            <PanelLeftOpen size={18} />
          </button>
        )}
        <div className="page-title">
          <h1>Documents</h1>
          <p>Bills, receipts and invoices you have uploaded.</p>
        </div>
        <button
          className="icon-btn"
          onClick={() => refresh()}
          title="Refresh"
          aria-label="Refresh document list"
        >
          <RefreshCw size={16} />
        </button>
      </header>

      <div className="page-body">
        <button
          type="button"
          className={`dropzone ${isDragging ? "dragging" : ""}`}
          onClick={() => fileInputRef.current?.click()}
        >
          <Upload size={22} />
          <span className="dropzone-main">
            {isDragging ? "Drop to upload" : "Drop files here, or click to choose"}
          </span>
          <span className="dropzone-sub">PDF, JPG or PNG · up to 10 MB each</span>
        </button>

        <input
          ref={fileInputRef}
          type="file"
          accept={ACCEPT}
          multiple
          hidden
          onChange={(e) => { handleFiles(e.target.files); e.target.value = ""; }}
        />

        {uploading.length > 0 && (
          <ul className="upload-queue">
            {uploading.map((name, i) => (
              <li key={`${name}-${i}`}>
                <LoaderCircle size={14} className="spin" />
                Uploading {name}…
              </li>
            ))}
          </ul>
        )}

        {proposal && (
          <ProposalCard
            proposal={proposal}
            saving={savingExpense}
            onConfirm={handleConfirmProposal}
            onDiscard={() => setProposal(null)}
          />
        )}

        {confirmedNote && (
          <div className="page-confirmed" role="status">
            <Check size={15} />
            <span>{confirmedNote}</span>
          </div>
        )}

        {error && (
          <div className="page-error" role="alert">
            <AlertCircle size={15} />
            <span>{error}</span>
          </div>
        )}

        {loadState === "loading" && (
          <div className="page-placeholder">
            <LoaderCircle size={20} className="spin" />
            <span>Loading your documents…</span>
          </div>
        )}

        {loadState === "error" && (
          <div className="page-placeholder">
            <span>Could not reach the server.</span>
            <button className="btn-secondary" onClick={() => refresh()}>Try again</button>
          </div>
        )}

        {loadState === "ready" && documents.length === 0 && (
          <div className="page-placeholder">
            <FileText size={22} />
            <span>No documents yet.</span>
            <span className="muted">Upload a receipt to get started.</span>
          </div>
        )}

        {loadState === "ready" && documents.length > 0 && (
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Type</th>
                  <th className="num">Size</th>
                  <th>Text</th>
                  <th>Uploaded</th>
                  <th><span className="sr-only">Actions</span></th>
                </tr>
              </thead>
              <tbody>
                {documents.map((doc) => {
                  const state = STATUS[doc.status] ?? STATUS.uploaded;
                  const StateIcon = state.Icon;
                  const isOpen = openTextId === doc.document_id;
                  const payload = textCache[doc.document_id];
                  return (
                  <Fragment key={doc.document_id}>
                  <tr className={confirmId === doc.document_id ? "confirming" : ""}>
                    <td>
                      <span className="cell-name">
                        {doc.mime_type.startsWith("image/")
                          ? <ImageIcon size={14} />
                          : <FileText size={14} />}
                        <span title={doc.original_filename}>{doc.original_filename}</span>
                      </span>
                    </td>
                    <td><span className="pill">{fileKind(doc.mime_type)}</span></td>
                    <td className="num">{formatBytes(doc.file_size)}</td>
                    <td>
                      <button
                        className={`extract-pill ${state.tone} ${doc.status === "ready" ? "clickable" : ""}`}
                        onClick={() => doc.status === "ready" && handleShowText(doc)}
                        disabled={doc.status !== "ready"}
                        title={doc.error_message || state.label}
                      >
                        <StateIcon size={12} className={state.spin ? "spin" : undefined} />
                        {state.label}
                        {doc.ocr_used && doc.status === "ready" && <span className="ocr-tag">OCR</span>}
                        {doc.status === "ready" && (isOpen ? <ChevronDown size={12} /> : <ChevronRight size={12} />)}
                      </button>
                    </td>
                    <td>{formatDate(doc.uploaded_at)}</td>
                    <td className="actions">
                      {doc.status === "ready" && (
                        <button
                          className="icon-btn"
                          onClick={() => handlePropose(doc)}
                          disabled={proposingId === doc.document_id}
                          title="Suggest an expense from this receipt"
                          aria-label={`Suggest an expense from ${doc.original_filename}`}
                        >
                          {proposingId === doc.document_id
                            ? <LoaderCircle size={15} className="spin" />
                            : <Sparkles size={15} />}
                        </button>
                      )}
                      {doc.status === "failed" && (
                        <button
                          className="icon-btn"
                          onClick={() => handleRetry(doc)}
                          disabled={busyId === doc.document_id}
                          title="Try reading this document again"
                          aria-label={`Retry reading ${doc.original_filename}`}
                        >
                          <RotateCw size={15} />
                        </button>
                      )}
                      <button
                        className="icon-btn"
                        onClick={() => handleDownload(doc)}
                        disabled={busyId === doc.document_id}
                        title="Download"
                        aria-label={`Download ${doc.original_filename}`}
                      >
                        <Download size={15} />
                      </button>
                      <button
                        className={`icon-btn danger ${confirmId === doc.document_id ? "armed" : ""}`}
                        onClick={() => handleDelete(doc)}
                        onBlur={() => confirmId === doc.document_id && setConfirmId(null)}
                        disabled={busyId === doc.document_id}
                        title={confirmId === doc.document_id ? "Click again to confirm" : "Delete"}
                        aria-label={
                          confirmId === doc.document_id
                            ? `Confirm deleting ${doc.original_filename}`
                            : `Delete ${doc.original_filename}`
                        }
                      >
                        {busyId === doc.document_id
                          ? <LoaderCircle size={15} className="spin" />
                          : <Trash2 size={15} />}
                      </button>
                    </td>
                  </tr>

                  {isOpen && (
                    <tr className="text-row">
                      <td colSpan={6}>
                        {textLoadingId === doc.document_id ? (
                          <div className="text-panel loading">
                            <LoaderCircle size={15} className="spin" /> Loading extracted text…
                          </div>
                        ) : (
                          <div className="text-panel">
                            <div className="text-panel-head">
                              <ScanText size={14} />
                              <span>
                                {payload?.char_count?.toLocaleString() ?? 0} characters
                                {payload?.ocr_used ? " · read by OCR" : " · read from the PDF text layer"}
                              </span>
                            </div>
                            {/* Shown exactly as extracted. Nothing here is a
                                confirmed expense until a person says so. */}
                            <pre className="text-panel-body">{payload?.text}</pre>
                          </div>
                        )}
                      </td>
                    </tr>
                  )}
                  </Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </main>
  );
}
