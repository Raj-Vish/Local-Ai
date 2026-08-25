import { useState } from "react";
import { Mail, Lock, Eye, EyeOff, Sparkles, LoaderCircle, AlertCircle, Sun, Moon } from "lucide-react";
import "../styles/auth.css";

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

// Owns the whole sign-in form. Because the credentials live here and this
// component unmounts on logout, they cannot survive into the next session.
export default function LoginView({ activeTheme, onToggleTheme, onAuthenticated }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState(null); // { field, message }
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (isSubmitting) return;

    if (!EMAIL_RE.test(email)) {
      setError({ field: "email", message: "Enter a valid corporate email address." });
      return;
    }
    if (password.length < 4) {
      setError({ field: "password", message: "Password must be at least 4 characters." });
      return;
    }

    setError(null);
    setIsSubmitting(true);

    // Mock auth. Swap this timeout for the real identity call.
    setTimeout(() => {
      setIsSubmitting(false);
      onAuthenticated({
        name: email.split("@")[0].replace(/[._-]+/g, " "),
        email,
        role: "Engineering"
      });
    }, 900);
  };

  const clearError = () => error && setError(null);
  const isDark = activeTheme === "dark";

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
          <h2>Company AI Assistant</h2>
          <p>Sign in to securely access internal resources.</p>
        </div>

        <form onSubmit={handleSubmit} className="auth-form" noValidate>
          <div className="input-group">
            <label htmlFor="login-email">Corporate Email</label>
            <div className="field">
              <Mail size={16} className="field-icon" />
              <input
                id="login-email"
                type="email"
                placeholder="name@company.com"
                value={email}
                autoComplete="email"
                autoFocus
                disabled={isSubmitting}
                aria-invalid={error?.field === "email" ? "true" : "false"}
                aria-describedby={error?.field === "email" ? "login-error" : undefined}
                onChange={(e) => { setEmail(e.target.value); clearError(); }}
              />
            </div>
          </div>

          <div className="input-group">
            <label htmlFor="login-password">Password</label>
            <div className="field">
              <Lock size={16} className="field-icon" />
              <input
                id="login-password"
                type={showPassword ? "text" : "password"}
                placeholder="••••••••"
                value={password}
                autoComplete="current-password"
                disabled={isSubmitting}
                aria-invalid={error?.field === "password" ? "true" : "false"}
                aria-describedby={error?.field === "password" ? "login-error" : undefined}
                onChange={(e) => { setPassword(e.target.value); clearError(); }}
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
              <span id="login-error" className="auth-error">
                <AlertCircle size={14} />
                {error.message}
              </span>
            )}
          </div>

          <button type="submit" className="btn-primary" disabled={isSubmitting}>
            {isSubmitting ? (
              <>
                <LoaderCircle size={16} className="spin" />
                Signing in…
              </>
            ) : (
              "Sign In"
            )}
          </button>
        </form>

        <p className="auth-footer">
          You will only see resources indexed for your department.
        </p>
      </div>
    </>
  );
}
