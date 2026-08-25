import { Sparkles } from "lucide-react";
import { SUGGESTED_PROMPTS } from "../data/mockData";

export default function EmptyState({ role, onPickPrompt }) {
  return (
    <div className="empty-state">
      <div className="empty-logo" aria-hidden="true">
        <Sparkles size={26} />
      </div>
      <h2>How can I help you today?</h2>
      <p className="empty-sub">Ask about policies, systems or anything indexed for {role}.</p>
      <div className="suggestions">
        {SUGGESTED_PROMPTS.map((prompt) => (
          <button key={prompt} type="button" className="suggestion" onClick={() => onPickPrompt(prompt)}>
            {prompt}
          </button>
        ))}
      </div>
    </div>
  );
}
