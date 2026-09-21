// Document calls. Everything goes through apiFetch, so the auth header and
// session-expiry handling come for free.
import { apiFetch } from "./client";

export function listDocuments(signal) {
  return apiFetch("/documents", { signal });
}

export function uploadDocument(file) {
  const form = new FormData();
  form.append("file", file);
  // No Content-Type set: the browser adds it with the multipart boundary,
  // which we would destroy by setting the header ourselves.
  return apiFetch("/documents/upload", { method: "POST", body: form });
}

// The text read out of a document. Kept off the list response because it can
// run to tens of thousands of characters; fetched only when actually shown.
export function getDocumentText(documentId, signal) {
  return apiFetch(`/documents/${documentId}/text`, { signal });
}

// Ask the server to read this document again -- after OCR is installed, or
// for a document uploaded before extraction existed.
export function retryExtraction(documentId) {
  return apiFetch(`/documents/${documentId}/extract`, { method: "POST" });
}

// Suggested expense fields read out of this document. Read-only: calling this
// creates nothing, so a proposal the user abandons leaves no trace.
export function proposeExpense(documentId, signal) {
  return apiFetch(`/documents/${documentId}/propose-expense`, { signal });
}

export function deleteDocument(documentId) {
  return apiFetch(`/documents/${documentId}`, { method: "DELETE" });
}

// The file needs the auth header, so it cannot be a plain <a href>. Fetch it
// as a blob, hand it to a temporary link, then release the object URL.
export async function downloadDocument(documentId, filename) {
  const base = import.meta.env.VITE_API_URL ?? "http://localhost:8000";
  const token = localStorage.getItem("expense_token");

  const response = await fetch(`${base}/documents/${documentId}/file`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!response.ok) throw new Error("Could not download that file.");

  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  // Without this the blob stays in memory for the life of the page.
  URL.revokeObjectURL(url);
}
