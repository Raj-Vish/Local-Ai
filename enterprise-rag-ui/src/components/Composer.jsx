import { useState, useRef } from "react";
import { Plus, Send, Square, X, FileText, Image as ImageIcon } from "lucide-react";
import { useOutsideClick } from "../hooks/useOutsideClick";

// The message box: staged attachments, the attach popover, the growing
// textarea, and the send/stop button. Owns only its own popover state.
export default function Composer({
  value, onChange, onSend, isGenerating, onStop,
  attachedFiles, onAttachFile, onRemoveFile, textareaRef
}) {
  const [isUploadOpen, setIsUploadOpen] = useState(false);
  const attachRef = useRef(null);
  const docInputRef = useRef(null);
  const photoInputRef = useRef(null);

  useOutsideClick(isUploadOpen, attachRef, () => setIsUploadOpen(false));

  const submit = (e) => {
    e.preventDefault();
    setIsUploadOpen(false);
    onSend();
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit(e);
    }
  };

  const handleFileSelect = (e, type) => {
    const file = e.target.files[0];
    if (file) {
      onAttachFile({ name: file.name, type });
      setIsUploadOpen(false);
    }
    e.target.value = null;
  };

  return (
    <div className="input-container">
      <div className="input-wrapper">
        {attachedFiles.length > 0 && (
          <div className="staged-files">
            {attachedFiles.map((f, i) => (
              <div key={i} className="staged-badge">
                {f.type === "photo" ? <ImageIcon size={12} /> : <FileText size={12} />}
                <span>{f.name}</span>
                <X size={12} className="remove-file" onClick={() => onRemoveFile(i)} />
              </div>
            ))}
          </div>
        )}

        <form onSubmit={submit} className="input-form">
          <div className="attachment-wrapper" ref={attachRef}>
            <button
              type="button"
              className="icon-btn"
              onClick={() => setIsUploadOpen(!isUploadOpen)}
              title="Attach a file"
              aria-label="Attach a file"
              aria-expanded={isUploadOpen}
            >
              <Plus size={20} />
            </button>

            {isUploadOpen && (
              <div className="popover-menu">
                <button type="button" className="popover-item" onClick={() => docInputRef.current?.click()}>
                  <FileText size={16} /> Upload Document
                </button>
                <button type="button" className="popover-item" onClick={() => photoInputRef.current?.click()}>
                  <ImageIcon size={16} /> Upload Photo
                </button>
              </div>
            )}
          </div>

          <input
            type="file" ref={docInputRef} style={{ display: "none" }}
            accept=".pdf,.doc,.docx,.xls,.xlsx,.csv,.txt"
            onChange={(e) => handleFileSelect(e, "document")}
          />
          <input
            type="file" ref={photoInputRef} style={{ display: "none" }}
            accept="image/*"
            onChange={(e) => handleFileSelect(e, "photo")}
          />

          <textarea
            ref={textareaRef}
            className="chat-input"
            rows={1}
            placeholder="Message Company AI Assistant..."
            value={value}
            onChange={(e) => onChange(e.target.value)}
            onKeyDown={handleKeyDown}
            aria-label="Message"
          />

          {isGenerating ? (
            <button
              type="button"
              className="send-btn active"
              onClick={onStop}
              title="Stop generating"
              aria-label="Stop generating"
            >
              <Square size={13} fill="currentColor" />
            </button>
          ) : (
            <button
              type="submit"
              className={`send-btn ${value.trim() ? "active" : ""}`}
              disabled={!value.trim()}
              title="Send"
              aria-label="Send message"
            >
              <Send size={16} />
            </button>
          )}
        </form>
      </div>
      <p className="input-footer">
        {isGenerating
          ? "Generating… press Stop to interrupt."
          : "AI can make mistakes. Verify important information."}
      </p>
    </div>
  );
}
