// Authentication calls. The token is stored here on success so no component
// has to remember to do it.
import { apiFetch, setAuthToken } from "./client";

export function register({ employeeId, fullName, email, password }) {
  return apiFetch("/auth/register", {
    method: "POST",
    body: {
      employee_id: employeeId,
      full_name: fullName,
      email,
      password,
    },
    skipAuthRedirect: true,
  });
}

export async function login({ email, password }) {
  const data = await apiFetch("/auth/login", {
    method: "POST",
    body: { email, password },
    // A wrong password is a 401 and must show an error, not fire the
    // session-expired logout.
    skipAuthRedirect: true,
  });
  setAuthToken(data.access_token);
  return data.user;
}

// Used on page load to turn a stored token back into a signed-in user.
export const getMe = () => apiFetch("/users/me");

export function logout() {
  setAuthToken(null);
}
