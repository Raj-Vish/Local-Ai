import { useState, useEffect, useRef, useCallback } from "react";
import {
  Upload, FileText, Image as ImageIcon, Download, Trash2,
  LoaderCircle, AlertCircle, PanelLeftOpen, RefreshCw
} from "lucide-react";
import { listDocuments, uploadDocument, deleteDocument, downloadDocument } from "../api/documents";
import { ApiError } from "../api/client";
import { formatBytes, formatDate, fileKind } from "../lib/format";
import "../styles/documents.css";

const ACCEPT = ".pdf,.jpg,.jpeg,.png";

export default function DocumentsPage({ isSidebarOpen, onOpenSidebar }) {
  const [documents, setDocuments] = useState([]);
  const [loadState, setLoadState] = useState("loading"); // loading | ready | error
  const [error, setError] = useState(null);
  const [uploading, setUploading] = useState([]);   // filenames in flight
  const [confirmId, setConfirmId] = useState(null); // delete armed for this id
  const [busyId, setBusyId] = useState(null);
  const [isDragging, setIsDragging] = useState(false);

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
                  <th>Uploaded</th>
                  <th><span className="sr-only">Actions</span></th>
                </tr>
              </thead>
              <tbody>
                {documents.map((doc) => (
                  <tr key={doc.document_id} className={confirmId === doc.document_id ? "confirming" : ""}>
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
                    <td>{formatDate(doc.uploaded_at)}</td>
                    <td className="actions">
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
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </main>
  );
}
