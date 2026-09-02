import { apiFetch } from "./client";

export const listReports = (signal) => apiFetch("/reports", { signal });

export const generateReport = (body) =>
  apiFetch("/reports/generate", { method: "POST", body });

export const deleteReport = (id) =>
  apiFetch(`/reports/${id}`, { method: "DELETE" });

// Needs the auth header, so it cannot be a plain link. Same approach as
// document downloads: fetch as a blob, click a temporary anchor, release it.
export async function downloadReport(reportId, reportName) {
  const base = import.meta.env.VITE_API_URL ?? "http://localhost:8000";
  const token = localStorage.getItem("expense_token");

  const response = await fetch(`${base}/reports/${reportId}/download`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!response.ok) throw new Error("Could not download that report.");

  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `${reportName}.xlsx`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}
