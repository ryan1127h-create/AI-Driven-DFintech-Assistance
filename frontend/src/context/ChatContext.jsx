import { createContext, useContext, useMemo, useState } from "react";

const ChatContext = createContext(null);

export function ChatProvider({ children }) {
  const [messages, setMessages] = useState([]);
  const [isStreaming, setIsStreaming] = useState(false);

  const addMessage = (msg) => setMessages((prev) => [...prev, msg]);
  const clearMessages = () => setMessages([]);

  const value = useMemo(
    () => ({
      messages,
      isStreaming,
      setIsStreaming,
      addMessage,
      clearMessages,
    }),
    [messages, isStreaming],
  );

  return <ChatContext.Provider value={value}>{children}</ChatContext.Provider>;
}

export function useChat() {
  const ctx = useContext(ChatContext);
  if (!ctx) throw new Error("useChat must be used within ChatProvider");
  return ctx;
}
