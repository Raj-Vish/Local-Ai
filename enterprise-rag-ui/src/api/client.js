// Every request to the backend goes through here. Nothing else in the app
// calls fetch directly, so the base URL, the auth header and error handling
// each exist in exactly one place.

const BASE_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

let authToken = null;

// Held in memory rather than localStorage: a script injected into the page
// can read localStorage, but not a module-scoped variable.
export function setAuthToken(token) {
  authToken = token;
}

export class ApiError extends Error {
  constructor(message, status, body) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
  }
}

export async function apiFetch(path, { method = "GET", body, signal } = {}) {
  const headers = {};
  if (authToken) headers.Authorization = `Bearer ${authToken}`;

  // FormData sets its own multipart boundary; setting Content-Type by hand
  // would overwrite it and the upload would fail to parse server-side.
  const isForm = body instanceof FormData;
  if (body && !isForm) headers["Content-Type"] = "application/json";

  let response;
  try {
    response = await fetch(`${BASE_URL}${path}`, {
      method,
      headers,
      body: isForm ? body : body ? JSON.stringify(body) : undefined,
      signal,
    });
  } catch (cause) {
    // fetch only rejects when the request never completed — server down,
    // DNS failure, CORS refusal. An HTTP error status resolves normally.
    if (cause.name === "AbortError") throw cause;
    throw new ApiError("Cannot reach the server.", 0, null);
  }

  if (response.status === 204) return null;

  const payload = await response.json().catch(() => null);

  if (!response.ok) {
    // FastAPI puts its message in `detail`; fall back to the status text.
    const message =
      (typeof payload?.detail === "string" && payload.detail) ||
      response.statusText ||
      "Request failed";
    throw new ApiError(message, response.status, payload);
  }

  return payload;
}

export const getHealth = (signal) => apiFetch("/health", { signal });
