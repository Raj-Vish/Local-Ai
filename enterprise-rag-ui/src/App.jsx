import "./styles/base.css";
import { useState, useEffect, useCallback } from "react";
import LoginView from "./components/LoginView";
import Sidebar from "./components/Sidebar";
import ChatView from "./components/ChatView";
import SettingsModal from "./components/SettingsModal";
import DocumentsPage from "./pages/DocumentsPage";
import ExpensesPage from "./pages/ExpensesPage";
import SessionLoader from "./components/SessionLoader";
import { useTheme } from "./hooks/useTheme";
import { useChatSession } from "./hooks/useChatSession";
import { getMe, logout } from "./api/auth";
import { loadStoredToken, setSessionExpiredHandler } from "./api/client";

export default function App() {
  const [user, setUser] = useState(null);
  // Derived during the first render rather than set from an effect: with no
  // stored token there is nothing to restore, and going straight to
  // "signed-out" avoids a wasted render pass.
  const [authState, setAuthState] = useState(() =>
    loadStoredToken() ? "restoring" : "signed-out"
  );
  const [expiredNotice, setExpiredNotice] = useState(false);
  const [activeView, setActiveView] = useState("chat");
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [memoryEnabled, setMemoryEnabled] = useState(true);

  const { themeSetting, setThemeSetting, activeTheme, toggleTheme } = useTheme();
  const chat = useChatSession();

  const endSession = useCallback(() => {
    logout();
    setUser(null);
    setIsSettingsOpen(false);
    setAuthState("signed-out");
  }, []);

  // A stored token is only a claim. Ask the server who it belongs to: it may
  // have expired, or the account may have been removed since it was issued.
  useEffect(() => {
    if (authState !== "restoring") return;
    let cancelled = false;
    getMe()
      .then((me) => {
        if (cancelled) return;
        setUser(me);
        setAuthState("signed-in");
      })
      .catch(() => {
        if (cancelled) return;
        logout();
        setAuthState("signed-out");
      });
    return () => { cancelled = true; };
    // Runs once: authState leaves "restoring" and never returns to it.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Any 401 from any request signs the user out, so every page added later
  // inherits session-expiry handling without writing a line for it.
  useEffect(() => {
    setSessionExpiredHandler(() => {
      setExpiredNotice(true);
      endSession();
    });
    return () => setSessionExpiredHandler(null);
  }, [endSession]);

  const handleLogout = () => {
    chat.startNewChat();
    setExpiredNotice(false);
    endSession();
  };

  const handleAuthenticated = (me) => {
    setExpiredNotice(false);
    setUser(me);
    setAuthState("signed-in");
  };

  const handleSelectThread = (topic, isRecent) => {
    chat.loadThread(topic, isRecent);
    if (window.innerWidth < 768) setIsSidebarOpen(false);
  };

  const handleNavigate = (view) => {
    setActiveView(view);
    // On a narrow screen the sidebar covers the page it just opened.
    if (window.innerWidth < 768) setIsSidebarOpen(false);
  };

  if (authState === "restoring") {
    return (
      <div className={`app-root theme-${activeTheme} auth-container`}>
        <SessionLoader />
      </div>
    );
  }

  if (!user) {
    return (
      <div className={`app-root theme-${activeTheme} auth-container`}>
        <LoginView
          activeTheme={activeTheme}
          onToggleTheme={toggleTheme}
          onAuthenticated={handleAuthenticated}
          expiredNotice={expiredNotice}
        />
      </div>
    );
  }

  return (
    <div className={`app-root theme-${activeTheme} workspace`}>
      {isSidebarOpen && (
        <Sidebar
          user={user}
          activeView={activeView}
          onNavigate={handleNavigate}
          recentChats={chat.recentChats}
          chatHistory={chat.chatHistory}
          activeChat={chat.activeChat}
          onClose={() => setIsSidebarOpen(false)}
          onNewChat={chat.startNewChat}
          onSelectThread={handleSelectThread}
          onOpenSettings={() => setIsSettingsOpen(true)}
          onLogout={handleLogout}
        />
      )}

      {activeView === "documents" ? (
        <DocumentsPage
          isSidebarOpen={isSidebarOpen}
          onOpenSidebar={() => setIsSidebarOpen(true)}
        />
      ) : activeView === "expenses" ? (
        <ExpensesPage
          isSidebarOpen={isSidebarOpen}
          onOpenSidebar={() => setIsSidebarOpen(true)}
        />
      ) : (
        <ChatView
          user={user}
          isSidebarOpen={isSidebarOpen}
          onOpenSidebar={() => setIsSidebarOpen(true)}
          messages={chat.messages}
          isGenerating={chat.isGenerating}
          inputValue={chat.inputValue}
          onInputChange={chat.setInputValue}
          onSend={chat.sendMessage}
          onStop={chat.stopGenerating}
          attachedFiles={chat.attachedFiles}
          onAttachFile={chat.attachFile}
          onRemoveFile={chat.removeFile}
          messagesEndRef={chat.messagesEndRef}
          textareaRef={chat.textareaRef}
        />
      )}

      {isSettingsOpen && (
        <SettingsModal
          user={user}
          onClose={() => setIsSettingsOpen(false)}
          themeSetting={themeSetting}
          setThemeSetting={setThemeSetting}
          activeTheme={activeTheme}
          memoryEnabled={memoryEnabled}
          setMemoryEnabled={setMemoryEnabled}
          historyCount={chat.historyCount}
          onClearHistory={chat.clearHistory}
        />
      )}
    </div>
  );
}
