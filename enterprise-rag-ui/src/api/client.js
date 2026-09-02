// Every request to the backend goes through here. Nothing else in the app
// calls fetch directly, so the base URL, the auth header, session expiry and
// error handling each exist in exactly one place.

const BASE_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";
const TOKEN_KEY = "expense_token";

let authToken = null;
let onSessionExpired = null;

// Kept in localStorage so a page refresh does not sign the user out. The
// trade-off: a script injected into the page could read it, where an
// in-memory variable could not. Acceptable for an internal LAN tool; a
// public app would use an httpOnly cookie the browser sends on its own.
export function loadStoredToken() {
  try {
    authToken = localStorage.getItem(TOKEN_KEY);
  } catch {
    // Private browsing and some hardened settings throw on access.
    authToken = null;
  }
  return authToken;
}

export function setAuthToken(token) {
  authToken = token;
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token);
    else localStorage.removeItem(TOKEN_KEY);
  } catch {
    // Storage unavailable: the session still works, it just will not
    // survive a refresh. Not worth failing the login over.
  }
}

// App registers one handler here. Any 401 from anywhere then logs out, so a
// page added later inherits expiry handling without doing anything.
export function setSessionExpiredHandler(handler) {
  onSessionExpired = handler;
}

export class ApiError extends Error {
  constructor(message, status, body) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
  }
}

// FastAPI returns validation problems as a list of objects; anything else as
// a plain string. Turn both into one sentence a person can act on.
function readErrorMessage(payload, response) {
  const detail = payload?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail) && detail.length) {
    const first = detail[0];
    const field = first.loc?.[first.loc.length - 1];
    const msg = (first.msg ?? "is invalid").replace(/^Value error,\s*/, "");
    return field ? `${String(field).replace(/_/g, " ")}: ${msg}` : msg;
  }
  return response.statusText || "Something went wrong. Please try again.";
}

export async function apiFetch(path, { method = "GET", body, signal, skipAuthRedirect } = {}) {
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
    // fetch only rejects when the request never completed — server down, DNS
    // failure, CORS refusal. An HTTP error status resolves normally.
    if (cause.name === "AbortError") throw cause;
    throw new ApiError("Cannot reach the server.", 0, null);
  }

  if (response.status === 204) return null;

  const payload = await response.json().catch(() => null);

  if (!response.ok) {
    // skipAuthRedirect exists for the login call itself: a wrong password is
    // a 401, and that must show an error rather than trigger a logout.
    if (response.status === 401 && !skipAuthRedirect) {
      setAuthToken(null);
      onSessionExpired?.();
    }
    throw new ApiError(readErrorMessage(payload, response), response.status, payload);
  }

  return payload;
}

export const getHealth = (signal) => apiFetch("/health", { signal });
