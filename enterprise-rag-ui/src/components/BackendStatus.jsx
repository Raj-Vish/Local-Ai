import { LoaderCircle, CheckCircle2, AlertTriangle, WifiOff } from "lucide-react";
import { useBackendHealth } from "../hooks/useBackendHealth";
import "../styles/status.css";

// Development aid: shows at a glance whether the API and MySQL are reachable,
// so "login isn't working" is never a mystery about which layer is down.
const STATES = {
  checking: { Icon: LoaderCircle, text: "Connecting to server…", tone: "wait", spin: true },
  ok: { Icon: CheckCircle2, text: "Server connected", tone: "ok" },
  degraded: { Icon: AlertTriangle, text: "Server up, database unreachable", tone: "warn" },
  offline: { Icon: WifiOff, text: "Cannot reach the server", tone: "bad" }
};

export default function BackendStatus() {
  const { status } = useBackendHealth();
  const { Icon, text, tone, spin } = STATES[status] ?? STATES.offline;

  return (
    <div className={`backend-status ${tone}`} role="status" aria-live="polite">
      <Icon size={13} className={spin ? "spin" : undefined} />
      <span>{text}</span>
    </div>
  );
}
