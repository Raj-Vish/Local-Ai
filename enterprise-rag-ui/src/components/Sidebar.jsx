import { User, Settings, LogOut, Plus, MessageSquare, PanelLeftClose, FolderOpen, Wallet, FileSpreadsheet } from "lucide-react";
import "../styles/sidebar.css";

function HistoryList({ topics, activeChat, keyPrefix, withIcon, onSelect }) {
  return (
    <div className="history-list">
      {topics.map((topic, idx) => (
        <button
          key={`${keyPrefix}-${idx}`}
          className={`history-item ${activeChat === topic ? "active" : ""}`}
          aria-current={activeChat === topic ? "true" : undefined}
          title={topic}
          onClick={() => onSelect(topic)}
        >
          {withIcon && <MessageSquare size={14} style={{ flexShrink: 0 }} />}
          <span className="history-text">{topic}</span>
        </button>
      ))}
    </div>
  );
}

const NAV = [
  { view: "chat", label: "Chat", Icon: MessageSquare },
  { view: "documents", label: "Documents", Icon: FolderOpen },
  { view: "expenses", label: "Expenses", Icon: Wallet },
  { view: "reports", label: "Reports", Icon: FileSpreadsheet }
];

export default function Sidebar({
  user, recentChats, chatHistory, activeChat, activeView,
  onClose, onNavigate, onNewChat, onSelectThread, onOpenSettings, onLogout
}) {
  return (
    <aside className="sidebar">
      <div className="sidebar-header">
        <div className="profile-group">
          <div className="avatar">
            <User size={16} />
          </div>
          <div className="profile-info">
            <span className="profile-name">{user?.full_name}</span>
            <span className="profile-role">{user?.employee_id}</span>
          </div>
        </div>
        <button className="icon-btn" onClick={onClose} title="Close sidebar" aria-label="Close sidebar">
          <PanelLeftClose size={18} />
        </button>
      </div>

      <div className="sidebar-scrollable">
        <nav className="nav-list" aria-label="Sections">
          {NAV.map(({ view, label, Icon }) => (
            <button
              key={view}
              className={`nav-item ${activeView === view ? "active" : ""}`}
              aria-current={activeView === view ? "page" : undefined}
              onClick={() => onNavigate(view)}
            >
              <Icon size={15} />
              {label}
            </button>
          ))}
        </nav>

        {activeView === "chat" && (
          <>
        <button className="new-chat-btn" onClick={onNewChat}>
          <Plus size={16} /> New Chat
        </button>

        {recentChats.length > 0 && (
          <>
            <div className="history-label">RECENT CHATS</div>
            <HistoryList
              topics={recentChats}
              activeChat={activeChat}
              keyPrefix="recent"
              withIcon
              onSelect={(topic) => onSelectThread(topic, true)}
            />
          </>
        )}

        <div className="history-label" style={{ marginTop: recentChats.length > 0 ? "24px" : "8px" }}>
          CHAT HISTORY
        </div>
        <HistoryList
          topics={chatHistory}
          activeChat={activeChat}
          keyPrefix="old"
          onSelect={(topic) => onSelectThread(topic, false)}
        />
          </>
        )}
      </div>

      <div className="sidebar-footer">
        <button className="footer-btn" onClick={onOpenSettings}>
          <Settings size={16} /> Settings
        </button>
        <button className="footer-btn danger" onClick={onLogout}>
          <LogOut size={16} /> Logout
        </button>
      </div>
    </aside>
  );
}
