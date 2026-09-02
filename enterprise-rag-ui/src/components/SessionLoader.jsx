import { LoaderCircle } from "lucide-react";

// Shown for the moment between page load and knowing whether the stored
// token is still good. Without it the login screen flashes on every refresh
// for someone who is already signed in.
export default function SessionLoader() {
  return (
    <div className="session-loader" role="status" aria-live="polite">
      <LoaderCircle size={22} className="spin" />
      <span>Restoring your session…</span>
    </div>
  );
}
