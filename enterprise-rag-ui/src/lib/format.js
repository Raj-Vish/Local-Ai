// Small display helpers shared by the document and expense screens.

export function formatBytes(bytes) {
  if (!bytes) return "0 KB";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function formatDate(iso) {
  if (!iso) return "";
  return new Date(iso).toLocaleDateString(undefined, {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

// "application/pdf" -> "PDF". Enough for a table column.
export function fileKind(mime) {
  if (mime === "application/pdf") return "PDF";
  if (mime === "image/jpeg") return "JPG";
  if (mime === "image/png") return "PNG";
  return "File";
}

// Amounts arrive from the server as strings so no precision is lost on the
// way. Formatted for display only -- never parsed and added up here.
export function formatMoney(amount, currency = "INR") {
  const value = Number(amount);
  if (Number.isNaN(value)) return String(amount);
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency,
    minimumFractionDigits: 2,
  }).format(value);
}

// "2026-08" -> first and last day of that month, as the API expects.
export function monthRange(month) {
  if (!month) return {};
  const [year, mon] = month.split("-").map(Number);
  const last = new Date(year, mon, 0).getDate();
  return { from: `${month}-01`, to: `${month}-${String(last).padStart(2, "0")}` };
}

export function currentMonth() {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
}

export function todayIso() {
  const now = new Date();
  const offset = now.getTimezoneOffset() * 60000;
  // toISOString() converts to UTC first, which can shift the date by a day.
  return new Date(now - offset).toISOString().slice(0, 10);
}
