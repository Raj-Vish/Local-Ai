import { useState } from "react";
import {
  Mail, Lock, Eye, EyeOff, Sparkles, LoaderCircle, AlertCircle,
  Sun, Moon, User, IdCard
} from "lucide-react";
import BackendStatus from "./BackendStatus";
import { login, register } from "../api/auth";
import { ApiError } from "../api/client";
import "../styles/auth.css";

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const EMPTY = { employeeId: "", fullName: "", email: "", password: "" };

// Owns sign-in and sign-up. Credentials live in this component's state and it
// unmounts on logout, so they cannot survive into the next session.
export default function LoginView({ activeTheme, onToggleTheme, onAuthenticated, expiredNotice }) {
  const [mode, setMode] = useState("signin"); // "signin" | "signup"
  const [form, setForm] = useState(EMPTY);
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState(null); // { field, message }
  const [notice, setNotice] = useState(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const isSignUp = mode === "signup";
  const set = (key) => (e) => {
    setForm((prev) => ({ ...prev, [key]: e.target.value }));
    if (error) setError(null);
  };

  const switchMode = () => {
    setMode(isSignUp ? "signin" : "signup");
    setError(null);
    setNotice(null);
    // Password is cleared but the email is kept, so someone who has just
    // registered does not retype it to sign in.
    setForm((prev) => ({ ...EMPTY, email: prev.email }));
  };

  // Checked here only to save a round trip on obvious mistakes. The server
  // validates everything again — the browser is never the authority.
  const findLocalProblem = () => {
    if (isSignUp && form.employeeId.trim().length < 2)
      return { field: "employeeId", message: "Enter your employee ID." };
    if (isSignUp && form.fullName.trim().length < 2)
      return { field: "fullName", message: "Enter your full name." };
    if (!EMAIL_RE.test(form.email))
      return { field: "email", message: "Enter a valid email address." };
    if (isSignUp && form.password.length < 8)
      return { field: "password", message: "Password must be at least 8 characters." };
    if (!form.password)
      return { field: "password", message: "Enter your password." };
    return null;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (isSubmitting) return;

    const problem = findLocalProblem();
    if (problem) {
      setError(problem);
      return;
    }

    setError(null);
    setNotice(null);
    setIsSubmitting(true);

    try {
      if (isSignUp) {
        await register(form);
        // Registering does not sign you in: the account is created, then the
        // password is entered once more. One less thing to go wrong, and it
        // confirms the password was typed as intended.
        setMode("signin");
        setForm((prev) => ({ ...EMPTY, email: prev.email }));
        setNotice("Account created. Please sign in.");
      } else {
        const user = await login(form);
        onAuthenticated(user);
      }
    } catch (err) {
      const message =
        err instanceof ApiError ? err.message : "Something went wrong. Please try again.";
      // Point at the email field for a duplicate account so the eye lands in
      // the right place; otherwise leave the message unattached.
      const field = err instanceof ApiError && err.status === 409 ? "email" : null;
      setError({ field, message });
    } finally {
      setIsSubmitting(false);
    }
  };

  const isDark = activeTheme === "dark";
  const invalid = (field) => (error?.field === field ? "true" : "false");
  const describedBy = (field) => (error?.field === field ? "auth-error" : undefined);

  return (
    <>
      <div className="auth-glow" aria-hidden="true" />

      <button
        type="button"
        className="auth-theme-toggle"
        onClick={onToggleTheme}
        title={isDark ? "Switch to light mode" : "Switch to dark mode"}
        aria-label={isDark ? "Switch to light mode" : "Switch to dark mode"}
      >
        {isDark ? <Sun size={16} /> : <Moon size={16} />}
      </button>

      <div className="auth-box">
        <div className="auth-header">
          <div className="auth-logo" aria-hidden="true">
            <Sparkles size={22} />
          </div>
          <h2>Expense Assistant</h2>
          <p>
            {isSignUp
              ? "Create your account to start recording expenses."
              : "Sign in to manage your expenses and reports."}
          </p>
        </div>

        <form onSubmit={handleSubmit} className="auth-form" noValidate>
          {isSignUp && (
            <>
              <div className="input-group">
                <label htmlFor="signup-employee">Employee ID</label>
                <div className="field">
                  <IdCard size={16} className="field-icon" />
                  <input
                    id="signup-employee"
                    type="text"
                    placeholder="EMP001"
                    value={form.employeeId}
                    autoComplete="off"
                    autoFocus
                    disabled={isSubmitting}
                    aria-invalid={invalid("employeeId")}
                    aria-describedby={describedBy("employeeId")}
                    onChange={set("employeeId")}
                  />
                </div>
              </div>

              <div className="input-group">
                <label htmlFor="signup-name">Full Name</label>
                <div className="field">
                  <User size={16} className="field-icon" />
                  <input
                    id="signup-name"
                    type="text"
                    placeholder="Raj Vishwakarma"
                    value={form.fullName}
                    autoComplete="name"
                    disabled={isSubmitting}
                    aria-invalid={invalid("fullName")}
                    aria-describedby={describedBy("fullName")}
                    onChange={set("fullName")}
                  />
                </div>
              </div>
            </>
          )}

          <div className="input-group">
            <label htmlFor="auth-email">Email</label>
            <div className="field">
              <Mail size={16} className="field-icon" />
              <input
                id="auth-email"
                type="email"
                placeholder="name@company.com"
                value={form.email}
                autoComplete="email"
                autoFocus={!isSignUp}
                disabled={isSubmitting}
                aria-invalid={invalid("email")}
                aria-describedby={describedBy("email")}
                onChange={set("email")}
              />
            </div>
          </div>

          <div className="input-group">
            <label htmlFor="auth-password">Password</label>
            <div className="field">
              <Lock size={16} className="field-icon" />
              <input
                id="auth-password"
                type={showPassword ? "text" : "password"}
                placeholder={isSignUp ? "At least 8 characters" : "••••••••"}
                value={form.password}
                autoComplete={isSignUp ? "new-password" : "current-password"}
                disabled={isSubmitting}
                aria-invalid={invalid("password")}
                aria-describedby={describedBy("password")}
                onChange={set("password")}
              />
              <button
                type="button"
                className="field-action"
                tabIndex={-1}
                onClick={() => setShowPassword(!showPassword)}
                title={showPassword ? "Hide password" : "Show password"}
                aria-label={showPassword ? "Hide password" : "Show password"}
              >
                {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>
          </div>

          <div className="auth-error-slot" aria-live="polite">
            {error && (
              <span id="auth-error" className="auth-error">
                <AlertCircle size={14} />
                {error.message}
              </span>
            )}
            {!error && notice && <span className="auth-notice">{notice}</span>}
            {!error && !notice && expiredNotice && (
              <span className="auth-error">
                <AlertCircle size={14} />
                Your session expired. Please sign in again.
              </span>
            )}
          </div>

          <button type="submit" className="btn-primary" disabled={isSubmitting}>
            {isSubmitting ? (
              <>
                <LoaderCircle size={16} className="spin" />
                {isSignUp ? "Creating account…" : "Signing in…"}
              </>
            ) : isSignUp ? (
              "Create Account"
            ) : (
              "Sign In"
            )}
          </button>
        </form>

        <p className="auth-switch">
          {isSignUp ? "Already have an account?" : "New here?"}{" "}
          <button type="button" className="link-btn" onClick={switchMode} disabled={isSubmitting}>
            {isSignUp ? "Sign in" : "Create an account"}
          </button>
        </p>

        <p className="auth-footer">
          You will only see expenses and documents you uploaded yourself.
        </p>

        <div className="auth-status">
          <BackendStatus />
        </div>
      </div>
    </>
  );
}
