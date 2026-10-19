import { useEffect, useState } from "react";
import { NavLink, useNavigate, useSearchParams } from "react-router-dom";
import {
  CheckCircle,
  ChevronLeft,
  LifeBuoy,
  MessageSquare,
  Pencil,
  Pin,
  PinOff,
  Plus,
  Trash2,
  User,
  X,
} from "lucide-react";
import { useRole } from "../../context/RoleContext";
import { useChat } from "../../context/ChatContext";
import { STAGE_LABELS, pagesForStage } from "../../data/stages";
import { cn } from "../../utils/cn";
import { formatDateTime } from "../../utils/format";
import nusLogo from "../../assets/nus_logo.png";
import AccountMenu from "../settings/AccountMenu";
import SettingsDialog from "../settings/SettingsDialog";
import { getChatSessions, clearChat, logout as apiLogout } from "../../../api";

function toConversation(conversation) {
  const turns = conversation.turn_count;
  return {
    id: conversation.session_id,
    title: conversation.preview || "Conversation",
    lastAccessedLabel: formatDateTime(conversation.updated_at) || "Recently",
    turnsLabel: `${turns} ${turns === 1 ? "turn" : "turns"}`,
    pinned: false,
  };
}

export default function StudentSidebar() {
  const { user, lifecycleStage, logout } = useRole();
  const { clearMessages, conversationsVersion } = useChat();
  const navigate = useNavigate();
  const [collapsed, setCollapsed] = useState(false);
  const [conversations, setConversations] = useState([]);
  const [editingId, setEditingId] = useState(null);
  const [editTitle, setEditTitle] = useState("");
  const [showActions, setShowActions] = useState(null);
  const [sessionsLoading, setSessionsLoading] = useState(false);
  // ?settings=<section> opens the settings dialog, from here or any page.
  const [searchParams, setSearchParams] = useSearchParams();
  const settingsSection = searchParams.get("settings");
  const setSettingsSection = (section) =>
    setSearchParams((params) => {
      const next = new URLSearchParams(params);
      if (section) next.set("settings", section);
      else next.delete("settings");
      return next;
    });
  const settingsDialog = settingsSection && (
    <SettingsDialog section={settingsSection} onSection={setSettingsSection} onClose={() => setSettingsSection(null)} />
  );

  const navItems = [
    { key: "profile", to: "/workspace/profile", label: "Profile", icon: User },
    ...pagesForStage(lifecycleStage),
    ...(user?.role === "enrolled_student"
      ? [{ key: "alumni-match", to: "/alumni-match", label: "Alumni Match", icon: MessageSquare }]
      : []),
    { key: "support", to: "/workspace/support", label: "Requests to Staff", icon: LifeBuoy },
  ];

  // Loaded once per user, then reloaded quietly (no loading state) whenever
  // a chat turn changes the list; local pins and renames are kept.
  useEffect(() => {
    let active = true;
    if (conversationsVersion === 0) setSessionsLoading(true);
    getChatSessions()
      .then((response) => {
        if (!active) return;
        setConversations((prev) => {
          const local = Object.fromEntries(prev.map((c) => [c.id, c]));
          return (response.conversations || []).map((conversation) => {
            const next = toConversation(conversation);
            const kept = local[next.id];
            return kept ? { ...next, title: kept.title, pinned: kept.pinned } : next;
          });
        });
      })
      .catch((error) => console.error("Unable to load conversations:", error))
      .finally(() => {
        if (active) setSessionsLoading(false);
      });
    return () => {
      active = false;
    };
  }, [user?.id, conversationsVersion]);

  const handleLogout = async () => {
    try {
      await apiLogout();
    } catch (err) {
      console.error(err);
    }
    logout(navigate);
  };

  const startNewChat = () => {
    clearMessages();
    navigate("/app", { replace: true });
  };

  const openConversation = (c) => {
    navigate(`/app?session=${encodeURIComponent(c.id)}`);
    setShowActions(null);
  };

  const renameConversation = (id) => {
    setConversations((prev) => prev.map((c) => (c.id === id ? { ...c, title: editTitle || c.title } : c)));
    setEditingId(null);
    setEditTitle("");
    setShowActions(null);
  };

  const deleteConversation = async (id) => {
    setShowActions(null);
    if (!window.confirm("Delete this conversation? This cannot be undone.")) return;

    try {
      await clearChat(id);
    } catch (error) {
      console.error("Unable to delete conversation:", error);
      alert(error.message || "Failed to delete the conversation. Please try again.");
      return;
    }

    setConversations((prev) => prev.filter((c) => c.id !== id));

    // The open conversation is gone server-side too: go back to a fresh chat
    // rather than leaving the pane showing a deleted session.
    const openSessionId = new URLSearchParams(window.location.search).get("session");
    if (openSessionId === id) startNewChat();
  };

  const togglePin = (id) => {
    setConversations((prev) => prev.map((c) => (c.id === id ? { ...c, pinned: !c.pinned } : c)));
    setShowActions(null);
  };

  const startRename = (c) => {
    setEditingId(c.id);
    setEditTitle(c.title);
    setShowActions(null);
  };

  const sortedConversations = [...conversations].sort((a, b) => (b.pinned ? 1 : 0) - (a.pinned ? 1 : 0));

  if (collapsed) {
    return (
      <div className="w-16 flex-shrink-0 flex flex-col items-center py-4 border-r border-app-subtle glass">
        <button onClick={() => setCollapsed(false)} className="sidebar-item justify-center w-10" title="Expand">
          <ChevronLeft size={18} className="rotate-180" />
        </button>
        <button
          onClick={startNewChat}
          className="btn-primary mt-4 flex h-10 w-10 !p-0 rounded-xl text-white"
          title="New Chat"
        >
          <Plus size={20} />
        </button>
        <nav className="mt-4 flex w-full flex-col items-center gap-1" aria-label="Student navigation">
          {navItems.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.key}
                to={item.to}
                title={item.label}
                aria-label={item.label}
                className={({ isActive }) => cn(
                  "sidebar-item h-10 w-10 justify-center px-0",
                  isActive && "sidebar-item-active",
                )}
              >
                <Icon size={16} />
              </NavLink>
            );
          })}
        </nav>
        <div className="mt-auto">
          <AccountMenu compact user={user} onSettings={() => setSettingsSection("account")} onLogout={handleLogout} />
        </div>
        {settingsDialog}
      </div>
    );
  }

  return (
    <div className="w-72 flex-shrink-0 flex flex-col border-r border-app-subtle glass">
      <div className="flex items-center justify-between px-4 py-4">
        <button onClick={() => navigate("/app", { replace: true })} className="flex items-center gap-2.5">
          <div className="flex h-10 w-18 items-center justify-center rounded-xl overflow-hidden">
            <img src={nusLogo} alt="NUS Logo" className="h-full w-full object-cover" />
          </div>
          <div className="text-left">
            <p className="font-display text-sm font-bold text-app-primary leading-tight">NUS DFT</p>
            <p className="text-[10px] text-app-muted">Lifecycle Assistant</p>
          </div>
        </button>
        <button onClick={() => setCollapsed(true)} className="text-app-faint hover:text-app-primary transition" title="Collapse">
          <ChevronLeft size={16} />
        </button>
      </div>

      <div className="px-3 pb-2">
        <button onClick={startNewChat} className="btn-primary w-full justify-center">
          <Plus size={16} />
          New Chat
        </button>
      </div>

      <div className="px-3 py-2">
        <p className="px-2 mb-2 text-[10px] font-semibold uppercase tracking-wider text-app-faint">Quick Access</p>
        <div className="space-y-0.5">
          {navItems.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.key}
                to={item.to}
                className={({ isActive }) => cn("sidebar-item w-full text-left", isActive && "sidebar-item-active")}
              >
                <Icon size={13} />
                <span className="text-sm">{item.label}</span>
              </NavLink>
            );
          })}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-3 py-2">
        <p className="px-2 mb-2 text-[10px] font-semibold uppercase tracking-wider text-app-faint">Chats</p>
        <div className="space-y-0.5">
          {sessionsLoading ? (
            <p className="text-xs text-app-faint px-3 py-4 text-center">Loading conversations...</p>
          ) : sortedConversations.map((c) => (
            <div key={c.id} className="relative group">
              {editingId === c.id ? (
                <div className="flex items-center gap-2 px-3 py-2">
                  <input
                    autoFocus
                    value={editTitle}
                    onChange={(e) => setEditTitle(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && renameConversation(c.id)}
                    onBlur={() => renameConversation(c.id)}
                    className="flex-1 bg-app-elevated border border-brand-400/30 rounded-lg px-2 py-1 text-xs text-app-primary focus:outline-none focus:ring-1 focus:ring-brand-500/50"
                  />
                  <button onClick={() => renameConversation(c.id)} className="text-emerald2-400 hover:text-emerald2-500">
                    <CheckCircle size={14} />
                  </button>
                  <button onClick={() => setEditingId(null)} className="text-app-faint hover:text-red-400">
                    <X size={14} />
                  </button>
                </div>
              ) : (
                <>
                  <button className="sidebar-item w-full text-left pr-8" onClick={() => openConversation(c)}>
                    {c.pinned ? (
                      <Pin size={14} className="flex-shrink-0 text-brand-400 fill-brand-400/20" />
                    ) : (
                      <MessageSquare size={14} className="flex-shrink-0 text-app-faint" />
                    )}
                    <div className="flex-1 min-w-0">
                      <span className="truncate block text-xs">{c.title}</span>
                      <div className="flex items-center gap-1.5 mt-0.5">
                        <span className="text-[10px] text-app-faint">{c.lastAccessedLabel}</span>
                        <span className="text-[10px] text-app-faint">·</span>
                        <span className="text-[10px] font-medium text-emerald2-400">{c.turnsLabel}</span>
                      </div>
                    </div>
                  </button>
                  <button
                    onClick={(e) => { e.stopPropagation(); setShowActions(showActions === c.id ? null : c.id); }}
                    className="absolute right-1 top-1/2 -translate-y-1/2 p-1 rounded text-app-faint hover:text-app-primary hover:bg-app-hover opacity-0 group-hover:opacity-100 transition"
                  >
                    <Pencil size={12} />
                  </button>
                  {showActions === c.id && (
                    <div className="absolute right-0 top-9 z-20 w-36 rounded-lg glass border border-app-subtle shadow-glass py-1">
                      <button onClick={() => togglePin(c.id)} className="flex items-center gap-2 w-full px-3 py-1.5 text-xs text-app-secondary hover:text-app-primary hover:bg-app-hover transition">
                        {c.pinned ? <PinOff size={12} /> : <Pin size={12} />}
                        {c.pinned ? "Unpin" : "Pin"}
                      </button>
                      <button onClick={() => startRename(c)} className="flex items-center gap-2 w-full px-3 py-1.5 text-xs text-app-secondary hover:text-app-primary hover:bg-app-hover transition">
                        <Pencil size={12} /> Rename
                      </button>
                      <button onClick={() => deleteConversation(c.id)} className="flex items-center gap-2 w-full px-3 py-1.5 text-xs text-red-400 hover:bg-app-hover transition">
                        <Trash2 size={12} /> Delete
                      </button>
                    </div>
                  )}
                </>
              )}
            </div>
          ))}
        </div>
      </div>

      <div className="px-3 py-3 border-t border-app-subtle">
        <AccountMenu user={user} subtitle={STAGE_LABELS[lifecycleStage] || ""}
          onSettings={() => setSettingsSection("account")} onLogout={handleLogout} />
      </div>
      {settingsDialog}
    </div>
  );
}
