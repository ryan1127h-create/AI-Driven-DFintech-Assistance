import { useEffect, useState } from "react";
import { NavLink, useNavigate } from "react-router-dom";
import {
  Plus,
  MessageSquare,
  Bookmark,
  Map,
  Bell,
  GraduationCap,
  LogOut,
  ChevronLeft,
  Compass,
  BookOpen,
  TrendingUp,
  GitCompare,
  HelpCircle,
  Activity,
  FileText,
  ListChecks,
  CalendarClock,
  Lightbulb,
  CheckCircle,
  CalendarPlus,
  Home,
  Users,
  User,
  Calendar,
  DollarSign,
  Briefcase,
  CheckSquare,
  Network,
  HandHeart,
  Star,
  Pin,
  PinOff,
  Pencil,
  Trash2,
  X,
} from "lucide-react";
import { useRole } from "../../context/RoleContext";
import { ROLE_META, ROLES } from "../../data/roles";
import { recentConversations as initialConversations, savedPlans, notifications } from "../../data/conversations";
import { cn } from "../../utils/cn";
import nusLogo from "../../assets/nus_logo.png";
import { getChatSessions, logout as apiLogout } from "../../../api";

const workspaceNav = {
  [ROLES.PROSPECTIVE]: [
    { to: "/workspace/discover", label: "Programme Overview", icon: "Compass" },
    { to: "/workspace/curriculum", label: "Courses", icon: "BookOpen" },
    { to: "/workspace/careers", label: "Career Outcomes", icon: "TrendingUp" },
    { to: "/workspace/compare", label: "Compare Programmes", icon: "GitCompare" },
    { to: "/workspace/faqs", label: "FAQs", icon: "HelpCircle" },
  ],
  [ROLES.APPLICANT]: [
    { to: "/workspace/application", label: "Application Status", icon: "Activity" },
    { to: "/workspace/documents", label: "Documents", icon: "FileText" },
    { to: "/workspace/checklist", label: "Checklist", icon: "ListChecks" },
    { to: "/workspace/deadlines", label: "Deadlines", icon: "CalendarClock" },
    { to: "/workspace/guidance", label: "Application Guidance", icon: "Lightbulb" },
  ],
  [ROLES.ADMITTED]: [
    { to: "/workspace/offer", label: "Offer Acceptance", icon: "CheckCircle" },
    { to: "/workspace/registration", label: "Registration", icon: "CalendarPlus" },
    { to: "/workspace/housing", label: "Housing", icon: "Home" },
    { to: "/workspace/orientation", label: "Orientation", icon: "Users" },
    { to: "/workspace/dates", label: "Important Dates", icon: "Calendar" },
  ],
  [ROLES.ENROLLED]: [
    { to: "/workspace/planner", label: "Degree Planner", icon: "Map" },
    { to: "/workspace/progress", label: "Academic Progress", icon: "TrendingUp" },
    { to: "/workspace/financial-aid", label: "Financial Aid", icon: "DollarSign" },
    { to: "/workspace/resources", label: "Learning Resources", icon: "BookOpen" },
    { to: "/workspace/career-guidance", label: "Career Guidance", icon: "Briefcase" },
  ],
  [ROLES.GRADUATING]: [
    { to: "/workspace/audit", label: "Graduation Audit", icon: "CheckSquare" },
    { to: "/workspace/tracker", label: "Requirement Tracker", icon: "ListChecks" },
    { to: "/workspace/transcript", label: "Transcript", icon: "FileText" },
    { to: "/workspace/career-prep", label: "Career Preparation", icon: "Briefcase" },
    { to: "/workspace/alumni-preview", label: "Alumni Preview", icon: "Users" },
  ],
  [ROLES.ALUMNI]: [
    { to: "/workspace/networking", label: "Networking", icon: "Network" },
    { to: "/workspace/mentoring", label: "Mentoring", icon: "HandHeart" },
    { to: "/workspace/events", label: "Events", icon: "Calendar" },
    { to: "/workspace/career-services", label: "Career Services", icon: "Briefcase" },
    { to: "/workspace/stories", label: "Alumni Stories", icon: "Star" },
  ],
};

const iconMap = {
  Compass, BookOpen, TrendingUp, GitCompare, HelpCircle, Activity, FileText,
  ListChecks, CalendarClock, Lightbulb, CheckCircle, CalendarPlus, Home, Users,
  Calendar, Map, DollarSign, Briefcase, CheckSquare, Network, HandHeart, Star,
};

const statusColors = {
  active: "text-emerald2-400",
  resolved: "text-app-faint",
  archived: "text-app-faint",
};

const notifDot = {
  warning: "bg-amber-400",
  info: "bg-brand-400",
  success: "bg-emerald2-400",
  deadline: "bg-red-400",
};

export default function StudentSidebar() {
  const { user, logout } = useRole();
  const navigate = useNavigate();
  const [collapsed, setCollapsed] = useState(false);
  const [tab, setTab] = useState("recent");
  const [conversations, setConversations] = useState(initialConversations);
  const [editingId, setEditingId] = useState(null);
  const [editTitle, setEditTitle] = useState("");
  const [showActions, setShowActions] = useState(null);
  const [sessionsLoading, setSessionsLoading] = useState(false);
  const meta = ROLE_META[user?.role];
  const wsNav = workspaceNav[user?.role] || [];

  useEffect(() => {
    let active = true;

    const loadSessions = async () => {
      setSessionsLoading(true);
      try {
        const response = await getChatSessions();
        console.log("chat session:", response);
        if (!active) return;

        setConversations(
          (response.conversations || []).map((conversation) => ({
            id: conversation.session_id,
            title: conversation.preview || "Conversation",
            lastAccessedLabel: conversation.updated_at
              ? new Date(conversation.updated_at).toLocaleString()
              : "Recently",
            role: user?.role,
            stage: `${conversation.turn_count} ${conversation.turn_count === 1 ? "turn" : "turns"}`,
            status: "active",
            pinned: false,
            saved: false,
          })),
        );
      } catch (error) {
        console.error("Unable to load conversations:", error);
      } finally {
        if (active) setSessionsLoading(false);
      }
    };

    loadSessions();
    return () => {
      active = false;
    };
  }, [user?.role]);

  const handleLogout = async () => {
    try {
      await apiLogout(); // call backend logout API
    } catch (err) {
      console.error(err);
    }

    logout(navigate); // clear context/local state and redirect
  };

  const handleProfile = () => {
    navigate("/workspace/profile");
  };

  const openConversation = (c) => {
    navigate(`/app?session=${encodeURIComponent(c.id)}`);
    setShowActions(null);
  };

  const renameConversation = (id) => {
    setConversations((prev) =>
      prev.map((c) => (c.id === id ? { ...c, title: editTitle || c.title } : c)),
    );
    setEditingId(null);
    setEditTitle("");
    setShowActions(null);
  };

  const deleteConversation = (id) => {
    setConversations((prev) => prev.filter((c) => c.id !== id));
    setShowActions(null);
  };

  const togglePin = (id) => {
    setConversations((prev) =>
      prev.map((c) => (c.id === id ? { ...c, pinned: !c.pinned } : c)),
    );
    setShowActions(null);
  };

  const startRename = (c) => {
    setEditingId(c.id);
    setEditTitle(c.title);
    setShowActions(null);
  };

  const visibleConversations = conversations
    .filter((c) => c.role === user?.role || c.saved)
    .sort((a, b) => (b.pinned ? 1 : 0) - (a.pinned ? 1 : 0));

  const savedConversations = conversations.filter((c) => c.saved);

  if (collapsed) {
    return (
      <div className="w-16 flex-shrink-0 flex flex-col items-center py-4 border-r border-app-subtle glass">
        <button onClick={() => setCollapsed(false)} className="sidebar-item justify-center w-10" title="Expand">
          <ChevronLeft size={18} className="rotate-180" />
        </button>
        <button
          onClick={() => navigate("/app", { replace: true })}
          className="mt-4 flex h-10 w-10 items-center justify-center rounded-xl bg-brand-500 text-app-primary hover:bg-brand-400 transition shadow-glow"
          title="New Chat"
        >
          <Plus size={20} />
        </button>
        <div className="mt-auto flex flex-col items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-full bg-brand-500/20 text-brand-300 text-sm font-medium">
            {user?.avatar}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="w-72 flex-shrink-0 flex flex-col border-r border-app-subtle glass">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-4">
        <button onClick={() => navigate("/app", { replace: true })} className="flex items-center gap-2.5">
          <div className="flex h-10 w-18 items-center justify-center rounded-xl overflow-hidden">
            <img
                src={nusLogo}
                alt="NUS Logo"
                className="h-full w-full object-cover"
            />
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

      {/* New Chat */}
      <div className="px-3 pb-2">
        <button onClick={() => navigate("/app", { replace: true })} className="btn-primary w-full justify-center">
          <Plus size={16} />
          New Chat
        </button>
      </div>

      {/* Scrollable area */}
      <div className="flex-1 overflow-y-auto px-3 py-2">
        {/* Conversation tabs */}
        <div className="flex gap-1 mb-2 px-1">
          {[
            { id: "recent", label: "Recent", icon: MessageSquare },
            // { id: "saved", label: "Saved", icon: Bookmark },
            // { id: "plans", label: "Plans", icon: Map },
          ].map((t) => {
            const TIcon = t.icon;
            return (
              <button
                key={t.id}
                onClick={() => setTab(t.id)}
                className={cn(
                  "flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs font-medium transition",
                  tab === t.id ? "bg-app-hover text-app-primary" : "text-app-muted hover:text-app-primary",
                )}
              >
                <TIcon size={13} />
                {t.label}
              </button>
            );
          })}
        </div>

        {tab === "recent" && (
          <div className="space-y-0.5">
            {sessionsLoading ? (
              <p className="text-xs text-app-faint px-3 py-4 text-center">Loading conversations...</p>
            ) : visibleConversations.map((c) => (
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
                    <button
                      className="sidebar-item w-full text-left pr-8"
                      onClick={() => openConversation(c)}
                    >
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
                          <span className={cn("text-[10px] font-medium", statusColors[c.status])}>{c.stage}</span>
                          {c.status === "resolved" && (
                            <span className="text-[10px] text-app-faint">· Resolved</span>
                          )}
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
        )}

        {tab === "saved" && (
          <div className="space-y-0.5">
            {savedConversations.length === 0 ? (
              <p className="text-xs text-app-faint px-3 py-4 text-center">No saved conversations yet.</p>
            ) : (
              savedConversations.map((c) => (
                <button key={c.id} className="sidebar-item w-full text-left" onClick={() => openConversation(c)}>
                  <Bookmark size={14} className="flex-shrink-0 text-brand-400" />
                  <div className="flex-1 min-w-0">
                    <span className="truncate block text-xs">{c.title}</span>
                    <span className="text-[10px] text-app-faint">{c.lastAccessedLabel} · {c.stage}</span>
                  </div>
                </button>
              ))
            )}
          </div>
        )}

        {tab === "plans" && (
          <div className="space-y-2">
            {savedPlans.map((p) => (
              <div key={p.id} className="rounded-lg p-3 bg-app-hover border border-app-subtle hover:border-brand-400/20 transition cursor-pointer">
                <p className="text-sm text-app-primary font-medium truncate">{p.title}</p>
                <p className="text-xs text-app-muted mt-0.5">{p.updated}</p>
                <div className="mt-2 h-1.5 rounded-full bg-app-hover overflow-hidden">
                  <div className="h-full bg-brand-500 rounded-full" style={{ width: `${p.progress}%` }} />
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Workspace section */}
        {/* <div className="mt-6 pt-4 border-t border-app-subtle">
          <p className="px-2 mb-2 text-[10px] font-semibold uppercase tracking-wider text-app-faint">
            {meta?.label} Workspace
          </p>
          <div className="space-y-0.5">
            {wsNav.map((item) => {
              const Icon = iconMap[item.icon] || MessageSquare;
              return (
                <NavLink
                  key={item.to}
                  to={item.to}
                  className={({ isActive }) => cn("sidebar-item w-full text-left", isActive && "sidebar-item-active")}
                >
                  <Icon size={14} className="flex-shrink-0" />
                  <span className="truncate">{item.label}</span>
                </NavLink>
              );
            })}
          </div>
        </div> */}

        {/* Notifications */}
        {/* <div className="mt-6 pt-4 border-t border-app-subtle">
          <div className="flex items-center gap-2 px-2 mb-2">
            <Bell size={13} className="text-app-faint" />
            <p className="text-[10px] font-semibold uppercase tracking-wider text-app-faint">Notifications</p>
          </div>
          <div className="space-y-1.5">
            {(notifications[user?.role] || notifications.prospective).slice(0, 3).map((n) => (
              <div key={n.id} className="rounded-lg p-2.5 bg-app-hover border border-app-soft">
                <div className="flex items-center gap-2">
                  <span className={cn("h-1.5 w-1.5 rounded-full flex-shrink-0", notifDot[n.type])} />
                  <p className="text-xs font-medium text-app-primary truncate">{n.title}</p>
                </div>
                <p className="text-[11px] text-app-muted mt-0.5 line-clamp-2">{n.body}</p>
                <p className="text-[10px] text-app-faint mt-1">{n.time}</p>
              </div>
            ))}
          </div>
        </div> */}
      </div>

      {/* User footer */}
      {/* <div className="px-3 py-3 border-t border-app-subtle">
        <div className="flex items-center gap-2.5 rounded-lg p-2 hover:bg-app-hover transition cursor-pointer" onClick={handleLogout}>
          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-brand-500/20 text-brand-300 text-xs font-medium flex-shrink-0">
            {user?.avatar}
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-app-primary truncate">{user?.name}</p>
            <p className="text-[10px] text-app-muted truncate">{meta?.label}</p>
          </div>
          <LogOut size={14} className="text-app-faint hover:text-red-400 transition" />
        </div>
      </div> */}
      <div className="px-3 py-3 border-t border-app-subtle">
        <div className="flex items-center gap-2.5 rounded-lg p-2 hover:bg-app-hover transition">
          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-brand-500/20 text-brand-300 text-xs font-medium flex-shrink-0">
            {user?.avatar}
          </div>

          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-app-primary truncate">
              {user?.name}
            </p>
            <p className="text-[10px] text-app-muted truncate">
              {meta?.label}
            </p>
          </div>

          {/* Profile */}
          <button
            onClick={handleProfile}
            className="p-1 text-app-faint hover:text-brand-400 transition"
            title="Profile"
          >
            <User size={14} />
          </button>

          {/* Logout */}
          <button
            onClick={handleLogout}
            className="p-1 text-app-faint hover:text-red-400 transition"
            title="Logout"
          >
            <LogOut size={14} />
          </button>
        </div>
      </div>
    </div>
  );
}
