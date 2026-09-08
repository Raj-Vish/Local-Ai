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

// Helper to load persistent data
const loadStored = (key, fallback) => {
  const saved = localStorage.getItem(key);
  return saved ? JSON.parse(saved) : fallback;
};

// Owns one conversation and the thread list around it.
export function useChatSession() {
  const [messages, setMessages] = useState(() => loadStored("ai_messages", []));
  const [inputValue, setInputValue] = useState("");
  const [isGenerating, setIsGenerating] = useState(false);
  const [attachedFiles, setAttachedFiles] = useState([]);

  const [recentChats, setRecentChats] = useState(() => loadStored("ai_recentChats", []));
  const [chatHistory, setChatHistory] = useState(() => loadStored("ai_chatHistory", INITIAL_CHAT_HISTORY));
  const [activeChat, setActiveChat] = useState(() => loadStored("ai_activeChat", null));

  // Save state changes to localStorage
  useEffect(() => { localStorage.setItem("ai_messages", JSON.stringify(messages)); }, [messages]);
  useEffect(() => { localStorage.setItem("ai_recentChats", JSON.stringify(recentChats)); }, [recentChats]);
  useEffect(() => { localStorage.setItem("ai_chatHistory", JSON.stringify(chatHistory)); }, [chatHistory]);
  useEffect(() => { localStorage.setItem("ai_activeChat", JSON.stringify(activeChat)); }, [activeChat]);

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

  const sendMessage = async () => {
    if (!inputValue.trim() || isGenerating) return;

    const userText = inputValue;
    setInputValue("");

    if (messages.length === 0) {
      setRecentChats((prev) => [userText, ...prev]);
      setActiveChat(userText);
    }

    setMessages((prev) => [...prev, { role: "user", content: userText, files: attachedFiles }]);
    setAttachedFiles([]);
    setIsGenerating(true);

    setMessages((prev) => [...prev, { role: "assistant", content: "" }]);

    try {
      // Connect to our FastAPI Python Backend and send FILES!
      const formData = new FormData();
      formData.append("message", userText);
      formData.append("user_role", "Employee");
      
      // If the user attached files, append them to the request
      attachedFiles.forEach(file => {
        formData.append("files", file);
      });

      const response = await fetch("http://localhost:8000/chat", {
        method: "POST",
        // Notice we do NOT set "Content-Type: application/json" anymore. 
        // The browser automatically sets it to "multipart/form-data" for us.
        body: formData
      });
      
      const data = await response.json();
      const aiReply = data.reply || "Error: No reply from AI.";
      
      // Break the real AI response into words for the streaming effect
      const tokens = aiReply.match(/\S+|\s+/g) || [];

      let i = 0;
      clearTimers();

      streamRef.current = setTimeout(() => {
        streamRef.current = setInterval(() => {
          if (i < tokens.length) {
            const nextToken = tokens[i];
            setMessages((prev) => {
              const updated = [...prev];
              const lastIndex = updated.length - 1;
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

    } catch (error) {
      console.error("Backend connection failed:", error);
      setMessages((prev) => {
        const updated = [...prev];
        updated[updated.length - 1] = {
          role: "assistant", 
          content: "Connection Error: Please ensure your FastAPI server (uvicorn server:app --reload) is running on port 8000."
        };
        return updated;
      });
      setIsGenerating(false);
    }
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
