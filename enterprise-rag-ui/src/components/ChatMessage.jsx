import { Sparkles, FileText, Image as ImageIcon, Copy, Check } from "lucide-react";

// One row in the thread. `isStreaming` marks the reply currently being written,
// which suppresses the copy action and shows the caret instead.
export default function ChatMessage({ message, isStreaming, isCopied, onCopy }) {
  const isAssistant = message.role === "assistant";
  const isThinking = isAssistant && !message.content && isStreaming;

  return (
    <div className={`message-row ${message.role}`}>
      {isAssistant && (
        <div className="assistant-avatar" aria-hidden="true">
          <Sparkles size={14} />
        </div>
      )}

      <div className={`message-bubble ${message.role}`}>
        {message.files?.length > 0 && (
          <div className="message-files">
            {message.files.map((f, i) => (
              <span key={i} className="file-badge">
                {f.type === "photo" ? <ImageIcon size={12} /> : <FileText size={12} />}
                {f.name}
              </span>
            ))}
          </div>
        )}

        {isThinking ? (
          <div className="typing" aria-label="Assistant is replying">
            <span /><span /><span />
          </div>
        ) : (
          <div className="message-text">
            {message.content}
            {isAssistant && isStreaming && <span className="caret" />}
          </div>
        )}

        {isAssistant && message.content && !isStreaming && (
          <div className="message-actions">
            <button
              type="button"
              className="msg-action"
              onClick={onCopy}
              title={isCopied ? "Copied" : "Copy"}
              aria-label="Copy message"
            >
              {isCopied ? <Check size={14} /> : <Copy size={14} />}
              {isCopied ? "Copied" : "Copy"}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
