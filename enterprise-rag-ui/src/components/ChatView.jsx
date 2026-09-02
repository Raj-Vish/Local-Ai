import { PanelLeft, Sparkles, Clock } from "lucide-react";
import ChatMessage from "./ChatMessage";
import "../styles/chat.css";

// The message list and bubbles are kept and working; the composer is not
// rendered, because it replies with canned text and in a demo that reads as
// a broken feature. The retrieval phase reconnects it to a real endpoint.
export default function ChatView({ isSidebarOpen, onOpenSidebar, messages, messagesEndRef }) {
  return (
    <main className="chat-main">
      <header className="chat-header">
        {!isSidebarOpen && (
          <button className="icon-btn" onClick={onOpenSidebar} title="Open sidebar" aria-label="Open sidebar">
            <PanelLeft size={20} />
          </button>
        )}
        <span className="header-title">Assistant</span>
        <span className="phase-badge">Next phase</span>
      </header>

      <div className="messages-container">
        <div className="messages-content">
          {messages.length === 0 ? (
            <div className="phase-notice">
              <div className="phase-icon" aria-hidden="true"><Sparkles size={22} /></div>
              <h2>Not connected yet</h2>
              <p>
                This screen is built and waiting. Asking questions about your own
                receipts needs the document-reading and retrieval work, which is
                the next phase of the project.
              </p>
              <p className="phase-meanwhile">
                <Clock size={13} />
                Meanwhile, Documents, Expenses and Reports are fully working.
              </p>
            </div>
          ) : (
            messages.map((msg, index) => (
              <ChatMessage key={index} message={msg} isStreaming={false} isCopied={false} onCopy={() => {}} />
            ))
          )}
          <div ref={messagesEndRef} style={{ height: "20px" }} />
        </div>
      </div>
    </main>
  );
}
