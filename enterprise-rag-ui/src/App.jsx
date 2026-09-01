import "./styles/base.css";
import { useState } from "react";
import LoginView from "./components/LoginView";
import Sidebar from "./components/Sidebar";
import ChatView from "./components/ChatView";
import SettingsModal from "./components/SettingsModal";
import { useTheme } from "./hooks/useTheme";
import { useChatSession } from "./hooks/useChatSession";

export default function App() {
  const [user, setUser] = useState(null);
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [memoryEnabled, setMemoryEnabled] = useState(true);

  const { themeSetting, setThemeSetting, activeTheme, toggleTheme } = useTheme();
  const chat = useChatSession();

  const handleLogout = () => {
    chat.startNewChat();
    setIsSettingsOpen(false);
    setUser(null);
  };

  const handleSelectThread = (topic, isRecent) => {
    chat.loadThread(topic, isRecent);
    if (window.innerWidth < 768) setIsSidebarOpen(false);
  };

  if (!user) {
    return (
      <div className={`app-root theme-${activeTheme} auth-container`}>
        <LoginView
          activeTheme={activeTheme}
          onToggleTheme={toggleTheme}
          onAuthenticated={setUser}
        />
      </div>
    );
  }

  return (
    <div className={`app-root theme-${activeTheme} workspace`}>
      {isSidebarOpen && (
        <Sidebar
          user={user}
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
