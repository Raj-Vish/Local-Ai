// Semantic search over your own documents. Like every other API wrapper, this
// goes through client.js, so the token, session expiry and error shaping are
// handled in one place.
//
// Note what these calls do NOT send: no user id, no document scope. The
// backend takes the user from the token, so the browser cannot widen a search
// beyond its own documents even if this file were tampered with.
import { apiFetch } from "./client";

// Retrieval only: returns matching chunks with their source documents.
export function searchDocuments({ query, topK }, signal) {
  return apiFetch("/rag/search", {
    method: "POST",
    body: { query, ...(topK ? { top_k: topK } : {}) },
    signal,
  });
}

// Retrieval plus, when a language service is configured, a phrased answer.
// Always returns the facts and sources, so the screen can show what was
// found even when no model is connected.
export function askQuestion({ question, topK }, signal) {
  return apiFetch("/rag/ask", {
    method: "POST",
    body: { question, ...(topK ? { top_k: topK } : {}) },
    signal,
  });
}

// How much of this user's material is searchable.
export const getIndexStatus = (signal) => apiFetch("/rag/status", { signal });
