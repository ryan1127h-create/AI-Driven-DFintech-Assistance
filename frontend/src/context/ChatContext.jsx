import { createContext, useContext, useMemo, useState } from "react";

const ChatContext = createContext(null);

export function ChatProvider({ children }) {
  const [messages, setMessages] = useState([]);
  const [isStreaming, setIsStreaming] = useState(false);

  const addMessage = (msg) => setMessages((prev) => [...prev, msg]);
  const clearMessages = () => setMessages([]);

  // Mutates the last message in place — used while a streaming reply is
  // coming in (appending path-timeline steps, appending answer tokens,
  // finalizing once the stream ends). `updater` receives the current last
  // message and returns its replacement.
  const updateLastMessage = (updater) => {
    setMessages((prev) => {
      if (prev.length === 0) return prev;
      const next = [...prev];
      next[next.length - 1] = updater(next[next.length - 1]);
      return next;
    });
  };

  // Drops the last `count` messages — used by the rollback feature (see
  // ChatWorkspace.jsx) after the backend has already deleted the
  // corresponding turns, to bring the local view back in sync.
  const removeLastMessages = (count) => {
    setMessages((prev) => prev.slice(0, Math.max(0, prev.length - count)));
  };

  const value = useMemo(
    () => ({
      messages,
      isStreaming,
      setIsStreaming,
      addMessage,
      clearMessages,
      updateLastMessage,
      removeLastMessages,
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
