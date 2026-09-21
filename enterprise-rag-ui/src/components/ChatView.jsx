import { useState, useEffect, useRef, useCallback } from "react";
import {
  PanelLeft, Search, LoaderCircle, FileText, AlertCircle,
  Database, Sparkles, CornerDownLeft
} from "lucide-react";
// askQuestion covers retrieval too, so searchDocuments (retrieval only) is
// not needed here; it stays in api/rag.js for callers that want no model step.
import { askQuestion, getIndexStatus } from "../api/rag";
import { ApiError } from "../api/client";
import "../styles/chat.css";

// Semantic search over this employee's own documents.
//
// What this screen honestly is right now: retrieval works, phrasing does not.
// Finding "the Mumbai hotel receipt" is done here, locally, by comparing
// meaning. Turning the result into a sentence needs the language model, which
// runs on a teammate's machine and is not connected yet. The screen says so
// rather than pretending.
//
// The figures under "From your records" are computed by MySQL, never by a
// model. That stays true once the model is connected: it will be given those
// numbers to phrase, and is told not to calculate.
export default function ChatView({ isSidebarOpen, onOpenSidebar }) {
  const [query, setQuery] = useState("");
  const [asking, setAsking] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [status, setStatus] = useState(null);
  const inputRef = useRef(null);

  const refreshStatus = useCallback(async (signal) => {
    try {
      setStatus(await getIndexStatus(signal));
    } catch { /* the banner simply does not appear */ }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    void (async () => { await refreshStatus(controller.signal); })();
    return () => controller.abort();
  }, [refreshStatus]);

  const submit = async (e) => {
    e.preventDefault();
    const text = query.trim();
    if (!text || asking) return;
    setAsking(true);
    setError(null);
    try {
      // /rag/ask returns retrieval plus a phrased answer when one is
      // available, so this one call covers both states.
      setResult(await askQuestion({ question: text }));
      await refreshStatus();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not search your documents.");
      setResult(null);
    } finally {
      setAsking(false);
    }
  };

  const nothingIndexed = status && status.chunks_indexed === 0;

  return (
    <main className="chat-main">
      <header className="chat-header">
        {!isSidebarOpen && (
          <button className="icon-btn" onClick={onOpenSidebar} title="Open sidebar" aria-label="Open sidebar">
            <PanelLeft size={20} />
          </button>
        )}
        <span className="header-title">Search your documents</span>
        {status && (
          <span className="phase-badge" title={`Embedding model: ${status.embed_model}`}>
            {status.chunks_indexed} chunk{status.chunks_indexed === 1 ? "" : "s"} indexed
          </span>
        )}
      </header>

      <div className="messages-container">
        <div className="messages-content">
          <form className="rag-search" onSubmit={submit}>
            <Search size={16} className="rag-search-icon" />
            <input
              ref={inputRef}
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Find my Mumbai hotel receipt…"
              disabled={asking}
              maxLength={500}
              aria-label="Search your documents"
            />
            <button type="submit" className="btn-primary compact" disabled={asking || !query.trim()}>
              {asking ? <LoaderCircle size={14} className="spin" /> : <CornerDownLeft size={14} />}
              {asking ? "Searching…" : "Search"}
            </button>
          </form>

          {nothingIndexed && (
            <div className="rag-notice">
              <Database size={14} />
              <span>
                Nothing is indexed yet. Upload a receipt on the Documents page — it is read
                and indexed automatically once it has been processed.
              </span>
            </div>
          )}

          {error && (
            <div className="page-error" role="alert">
              <AlertCircle size={15} /><span>{error}</span>
            </div>
          )}

          {result && (
            <div className="rag-result">
              {result.answer ? (
                <div className="rag-answer">
                  <div className="rag-answer-head"><Sparkles size={14} /> Answer</div>
                  <p>{result.answer}</p>
                </div>
              ) : (
                <div className="rag-notice subtle">
                  <AlertCircle size={14} />
                  <span>
                    {result.unavailable_reason} Retrieval below still works — only the
                    written answer needs the language service.
                  </span>
                </div>
              )}

              {result.facts?.length > 0 && (
                <div className="rag-facts">
                  <div className="rag-section-head">
                    From your records
                    {/* Said plainly, because it is the rule the project is built on. */}
                    <span className="rag-hint">computed by the database, not by a model</span>
                  </div>
                  <ul>{result.facts.map((f, i) => <li key={i}>{f}</li>)}</ul>
                </div>
              )}

              <div className="rag-section-head">
                {result.sources.length === 0
                  ? "No matching documents"
                  : `Matching documents (${result.sources.length})`}
              </div>

              {result.sources.length === 0 && !nothingIndexed && (
                <p className="rag-empty">
                  Nothing in your documents came close to that. Try different words —
                  the search matches meaning, so “where I slept” finds a hotel bill.
                </p>
              )}

              {result.sources.map((hit) => (
                <article key={hit.chunk_id} className="rag-hit">
                  <header>
                    <FileText size={13} />
                    <span className="rag-hit-name" title={hit.filename}>{hit.filename}</span>
                    <span className="rag-hit-meta">
                      lines {hit.start_line}–{hit.end_line}
                    </span>
                    {hit.score !== null && (
                      <span className="rag-score" title="Similarity: 1.00 is identical">
                        {hit.score.toFixed(2)}
                      </span>
                    )}
                  </header>
                  <pre>{hit.text}</pre>
                </article>
              ))}
            </div>
          )}
        </div>
      </div>
    </main>
  );
}
