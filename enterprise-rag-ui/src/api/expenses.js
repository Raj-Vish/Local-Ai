// Expense calls. Filters are sent to the server rather than applied here, so
// the rows and the total are always computed together and cannot disagree.
import { apiFetch } from "./client";

export const CATEGORIES = ["Hotel", "Transport", "Food", "Client", "Event", "Other"];

function query({ from, to, category } = {}) {
  const params = new URLSearchParams();
  if (from) params.set("from", from);
  if (to) params.set("to", to);
  if (category) params.set("category", category);
  const q = params.toString();
  return q ? `?${q}` : "";
}

export const listExpenses = (filters, signal) =>
  apiFetch(`/expenses${query(filters)}`, { signal });

export const getSummary = (filters, signal) =>
  apiFetch(`/expenses/summary${query(filters)}`, { signal });

export const createExpense = (body) =>
  apiFetch("/expenses", { method: "POST", body });

export const updateExpense = (id, body) =>
  apiFetch(`/expenses/${id}`, { method: "PATCH", body });

export const deleteExpense = (id) =>
  apiFetch(`/expenses/${id}`, { method: "DELETE" });
