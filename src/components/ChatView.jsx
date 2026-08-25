import { useState } from "react";
import { PanelLeft } from "lucide-react";
import ChatMessage from "./ChatMessage";
import EmptyState from "./EmptyState";
import Composer from "./Composer";
import { writeToClipboard } from "../lib/clipboard";
import "../styles/chat.css";

export default function ChatView({
  user, isSidebarOpen, onOpenSidebar,
  messages, isGenerating, inputValue, onInputChange, onSend, onStop,
  attachedFiles, onAttachFile, onRemoveFile,
  messagesEndRef, textareaRef
}) {
  const [copiedIndex, setCopiedIndex] = useState(null);

  const handleCopy = async (text, index) => {
    // Only confirm a copy that actually landed.
    if (!(await writeToClipboard(text))) return;
    setCopiedIndex(index);
    setTimeout(() => setCopiedIndex(null), 1500);
  };

  const pickPrompt = (prompt) => {
    onInputChange(prompt);
    textareaRef.current?.focus();
  };

  const lastIndex = messages.length - 1;

  return (
    <main className="chat-main">
      <header className="chat-header">
        {!isSidebarOpen && (
          <button className="icon-btn" onClick={onOpenSidebar} title="Open sidebar" aria-label="Open sidebar">
            <PanelLeft size={20} />
          </button>
        )}
        <span className="header-title">Company AI Assistant</span>
      </header>

      <div className="messages-container">
        <div className="messages-content">
          {messages.length === 0 ? (
            <EmptyState role={user?.role} onPickPrompt={pickPrompt} />
          ) : (
            messages.map((msg, index) => (
              <ChatMessage
                key={index}
                message={msg}
                isStreaming={isGenerating && index === lastIndex}
                isCopied={copiedIndex === index}
                onCopy={() => handleCopy(msg.content, index)}
              />
            ))
          )}
          <div ref={messagesEndRef} style={{ height: "20px" }} />
        </div>
      </div>

      <Composer
        value={inputValue}
        onChange={onInputChange}
        onSend={onSend}
        isGenerating={isGenerating}
        onStop={onStop}
        attachedFiles={attachedFiles}
        onAttachFile={onAttachFile}
        onRemoveFile={onRemoveFile}
        textareaRef={textareaRef}
      />
    </main>
  );
}
