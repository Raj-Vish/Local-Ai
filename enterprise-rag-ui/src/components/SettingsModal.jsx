import { useState } from "react";
import { X, User, Sun, Moon, Monitor, Trash2 } from "lucide-react";
import { useDialogA11y } from "../hooks/useDialogA11y";
import "../styles/settings.css";

const THEME_OPTIONS = [
  { value: "light", label: "Light", Icon: Sun },
  { value: "system", label: "System", Icon: Monitor },
  { value: "dark", label: "Dark", Icon: Moon }
];

export default function SettingsModal({
  user, onClose,
  themeSetting, setThemeSetting, activeTheme,
  memoryEnabled, setMemoryEnabled,
  historyCount, onClearHistory
}) {
  const [confirmClear, setConfirmClear] = useState(false);
  const panelRef = useDialogA11y(true, onClose);

  const handleClear = () => {
    // Two-step: the first click arms, the second wipes.
    if (!confirmClear) {
      setConfirmClear(true);
      return;
    }
    onClearHistory();
    setConfirmClear(false);
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div
        className="modal-content"
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="settings-title"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="modal-header">
          <h3 id="settings-title">Settings</h3>
          <button type="button" className="icon-btn" onClick={onClose} title="Close settings" aria-label="Close settings">
            <X size={18} />
          </button>
        </div>

        <div className="modal-body">
          <div className="setting-group">
            <span className="setting-label">Account</span>
            <div className="account-row">
              <div className="avatar" aria-hidden="true">
                <User size={16} />
              </div>
              <div className="account-info">
                <span className="account-name">{user?.full_name}</span>
                <span className="account-meta">{user?.email} &middot; {user?.employee_id}</span>
              </div>
            </div>
          </div>

          <div className="setting-group">
            <span className="setting-label" id="theme-label">Theme</span>
            <div className="theme-grid" role="group" aria-labelledby="theme-label">
              {THEME_OPTIONS.map(({ value, label, Icon }) => (
                <button
                  key={value}
                  type="button"
                  className={`theme-btn ${themeSetting === value ? "active" : ""}`}
                  aria-pressed={themeSetting === value}
                  onClick={() => setThemeSetting(value)}
                >
                  <Icon size={15} />
                  {label}
                </button>
              ))}
            </div>
            {themeSetting === "system" && (
              <p className="setting-sub">Following your device, currently {activeTheme}.</p>
            )}
          </div>

          <div className="setting-group flex-between">
            <div className="setting-text">
              <span className="setting-label" id="memory-label">Memory</span>
              <p className="setting-sub">Allow assistant to recall context across chats.</p>
            </div>
            <button
              type="button"
              role="switch"
              aria-checked={memoryEnabled}
              aria-labelledby="memory-label"
              className={`toggle-switch ${memoryEnabled ? "active" : ""}`}
              onClick={() => setMemoryEnabled(!memoryEnabled)}
            >
              <span className="toggle-circle" />
            </button>
          </div>

          <div className="setting-group flex-between">
            <div className="setting-text">
              <span className="setting-label">Conversation history</span>
              <p className="setting-sub">
                {confirmClear
                  ? "This cannot be undone. Click again to confirm."
                  : historyCount === 0
                    ? "No saved conversations."
                    : `${historyCount} saved ${historyCount === 1 ? "conversation" : "conversations"}.`}
              </p>
            </div>
            <button
              type="button"
              className={`btn-danger ${confirmClear ? "confirming" : ""}`}
              disabled={historyCount === 0}
              onClick={handleClear}
            >
              <Trash2 size={14} />
              {confirmClear ? "Confirm" : "Clear"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
