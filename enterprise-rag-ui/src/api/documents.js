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
