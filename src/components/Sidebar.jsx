import { User, Settings, LogOut, Plus, MessageSquare, PanelLeftClose } from "lucide-react";
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

export default function Sidebar({
  user, recentChats, chatHistory, activeChat,
  onClose, onNewChat, onSelectThread, onOpenSettings, onLogout
}) {
  return (
    <aside className="sidebar">
      <div className="sidebar-header">
        <div className="profile-group">
          <div className="avatar">
            <User size={16} />
          </div>
          <div className="profile-info">
            <span className="profile-name" style={{ textTransform: "capitalize" }}>{user?.name}</span>
            <span className="profile-role">{user?.role}</span>
          </div>
        </div>
        <button className="icon-btn" onClick={onClose} title="Close sidebar" aria-label="Close sidebar">
          <PanelLeftClose size={18} />
        </button>
      </div>

      <div className="sidebar-scrollable">
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
