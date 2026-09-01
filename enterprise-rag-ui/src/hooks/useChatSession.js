import { useState, useRef, useEffect } from "react";
import {
  MOCK_HISTORY_DATA,
  INITIAL_CHAT_HISTORY,
  buildMockReply,
  buildRecoveredThread
} from "../data/mockData";
import { useAutoGrow } from "./useAutoGrow";

const THINKING_MS = 450; // pause before the first token
const TOKEN_MS = 25;     // gap between tokens

// Owns one conversation and the thread list around it: the messages, the fake
// token stream, staged attachments and the sidebar history.
export function useChatSession() {
  const [messages, setMessages] = useState([]);
  const [inputValue, setInputValue] = useState("");
  const [isGenerating, setIsGenerating] = useState(false);
  const [attachedFiles, setAttachedFiles] = useState([]);

  const [recentChats, setRecentChats] = useState([]);
  const [chatHistory, setChatHistory] = useState(INITIAL_CHAT_HISTORY);
  const [activeChat, setActiveChat] = useState(null);

  const messagesEndRef = useRef(null);
  const streamRef = useRef(null);
  const textareaRef = useAutoGrow(inputValue);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isGenerating]);

  // A stream left running after unmount keeps writing to a thread nobody is viewing.
  useEffect(() => () => {
    clearTimeout(streamRef.current);
    clearInterval(streamRef.current);
  }, []);

  const clearTimers = () => {
    clearTimeout(streamRef.current);
    clearInterval(streamRef.current);
    streamRef.current = null;
  };

  const stopGenerating = () => {
    clearTimers();
    setIsGenerating(false);
    // Stopping before the first token arrives would otherwise strand an empty
    // reply bubble that can never fill in. Drop it; keep partial text as-is.
    setMessages((prev) => {
      const last = prev[prev.length - 1];
      return last && last.role === "assistant" && !last.content ? prev.slice(0, -1) : prev;
    });
  };

  const startNewChat = () => {
    stopGenerating();
    setMessages([]);
    setAttachedFiles([]);
    setActiveChat(null);
  };

  const loadThread = (topic, isRecent = false) => {
    stopGenerating();
    setActiveChat(topic);
    setMessages(isRecent ? buildRecoveredThread(topic) : MOCK_HISTORY_DATA[topic]);
  };

  const clearHistory = () => {
    setRecentChats([]);
    setChatHistory([]);
    startNewChat();
  };

  const sendMessage = () => {
    if (!inputValue.trim() || isGenerating) return;

    const userText = inputValue;
    setInputValue("");

    // The first message in a thread becomes its title in Recent Chats.
    if (messages.length === 0) {
      setRecentChats((prev) => [userText, ...prev]);
      setActiveChat(userText);
    }

    setMessages((prev) => [...prev, { role: "user", content: userText, files: attachedFiles }]);
    setAttachedFiles([]);
    setIsGenerating(true);

    const tokens = buildMockReply(userText).match(/\S+|\s+/g) || [];
    setMessages((prev) => [...prev, { role: "assistant", content: "" }]);

    let i = 0;
    clearTimers();

    // Hold before the first token so the thinking indicator is visible. A real
    // backend supplies this latency on its own; the delay goes away with it.
    streamRef.current = setTimeout(() => {
      streamRef.current = setInterval(() => {
        if (i < tokens.length) {
          const nextToken = tokens[i];
          setMessages((prev) => {
            const updated = [...prev];
            const lastIndex = updated.length - 1;
            // Clone the last message before editing it; mutating in place makes
            // React Strict Mode replay the append and double every word.
            updated[lastIndex] = {
              ...updated[lastIndex],
              content: updated[lastIndex].content + nextToken
            };
            return updated;
          });
          i++;
        } else {
          clearTimers();
          setIsGenerating(false);
        }
      }, TOKEN_MS);
    }, THINKING_MS);
  };

  const attachFile = (file) => setAttachedFiles((prev) => [...prev, file]);
  const removeFile = (index) => setAttachedFiles((prev) => prev.filter((_, i) => i !== index));

  return {
    messages, inputValue, setInputValue, isGenerating,
    attachedFiles, attachFile, removeFile,
    recentChats, chatHistory, activeChat,
    historyCount: recentChats.length + chatHistory.length,
    messagesEndRef, textareaRef,
    sendMessage, stopGenerating, startNewChat, loadThread, clearHistory
  };
}
