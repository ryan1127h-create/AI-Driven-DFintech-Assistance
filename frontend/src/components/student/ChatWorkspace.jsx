import { useState, useRef, useEffect } from "react";
import { useLocation } from "react-router-dom";
import {
  Send,
  Sparkles,
  Copy,
  ThumbsUp,
  ThumbsDown,
  RefreshCw,
  ChevronDown,
  Network,
  Bot,
  User,
  Search,
} from "lucide-react";
import { useRole } from "../../context/RoleContext";
import { useChat } from "../../context/ChatContext";
import { ROLE_META } from "../../data/roles";
import { suggestedPrompts, agents } from "../../data/conversations";
import {
  getProfile,
  updateProfile,
  createProfile,
  extractProfile,
  getChatHistory,
  sendMessage as apiSendMessage,
} from "../../../api";
import { cn } from "../../utils/cn";
import ThemeToggle from "../ThemeToggle";
import LandingStep from "./wizard/LandingStep";
import FormStep from "./wizard/FormStep";
import SettingsModal from "./wizard/SettingsModal";
import { LoadingSpinner } from "./apiWidgets";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

const WIZARD_LANDING = "landing";
const WIZARD_FORM = "form";
const CHAT = "chat";

const SETTINGS_STATUS = {
  configured: false,
  model: "deepseek-v4-pro",
  key_hint: "",
};

export default function ChatWorkspace() {
  const { user } = useRole();
  const { messages, addMessage, isStreaming, setIsStreaming, clearMessages } = useChat();
  const [view, setView] = useState(WIZARD_LANDING);
  const [landingData, setLandingData] = useState(null);
  const [profile, setProfile] = useState(null);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [profileChecked, setProfileChecked] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    let active = true;

    const checkProfile = async () => {
      setLoading(true);
      setError(null);

      try {
        const existingProfile = await getProfile();
        if (!active) return;

        if (existingProfile !== null) {
          setProfile(existingProfile);
          setView(CHAT);
        }
      } catch (err) {
        if (active) setError(err.message || "Unable to check your profile.");
      } finally {
        if (active) {
          setLoading(false);
          setProfileChecked(true);
        }
      }
    };

    checkProfile();
    return () => {
      active = false;
    };
  }, []);

  if (!profileChecked) {
    return <LoadingSpinner label="Checking your profile..." />;
  }

  const handleLandingAdvance = async (data) => {
    setLoading(true);
    setError(null);
    try {
      const response = data.cvFile
        ? await extractProfile(data)
        : {
            prefill: {
              lifecycle_stage: data.lifecycle_stage,
              profile_summary: data.text || "",
            },
          };
      setLandingData({ ...response.prefill, cvFile: data.cvFile });
      setView(WIZARD_FORM);
    } catch (err) {
      setError(err.message || "Unable to extract profile data.");
    } finally {
      setLoading(false);
    }
  };

  const handleGenerate = async (formProfile) => {
    setLoading(true);
    setError(null);
    try {
      const profilePayload = {
        lifecycle_stage: formProfile.lifecycle_stage === "applicant" ? "applicant" : "prospect" ,
        academic_background_raw: formProfile.academic_background_raw || null,
        academic_background_std: formProfile.academic_background_std || null,
        school_tier: formProfile.school_tier || null,
        tech_level_raw: formProfile.tech_level_raw || null,
        tech_level_std: formProfile.tech_level_std || null,
        work_years: formProfile.work_years === "" ? null : Number(formProfile.work_years),
        gmat: formProfile.gmat === "" ? null : Number(formProfile.gmat),
        gre: formProfile.gre === "" ? null : Number(formProfile.gre),
        toefl: formProfile.toefl === "" ? null : Number(formProfile.toefl),
        ielts: formProfile.ielts === "" ? null : Number(formProfile.ielts),
        target_role_raw: formProfile.target_role_raw || null,
        target_role_std: formProfile.target_role_std || null,
        target_industry_std: formProfile.target_industry_std || null,
        completed_courses: formProfile.completed_courses || [],
      };
      const savedProfile = profile
        ? await updateProfile(profilePayload)
        : await createProfile(profilePayload);
      setProfile(savedProfile);
      setView(CHAT);
    } catch (err) {
      setError(err.message || "Unable to generate analysis.");
    } finally {
      setLoading(false);
    }
  };

  const handleSkip = () => {
    clearMessages();
    setView(CHAT);
  };

  const handleStartWizard = () => {
    if (profile) {
      setView(CHAT);
      return;
    }

    setView(WIZARD_LANDING);
    setLandingData(null);
    setProfile(null);
    setError(null);
  };

  if (view === WIZARD_LANDING) {
    return (
      <div className="flex-1 flex flex-col h-full overflow-y-auto">
        <LandingStep
          onAdvance={handleLandingAdvance}
          onOpenSettings={() => setSettingsOpen(true)}
          onSkip={handleSkip}
          loading={loading}
          error={error}
        />
        {settingsOpen && <SettingsModal status={SETTINGS_STATUS} onClose={() => setSettingsOpen(false)} onSave={() => {}} />}
      </div>
    );
  }

  if (view === WIZARD_FORM) {
    return (
      <div className="flex-1 flex flex-col h-full overflow-y-auto">
        <FormStep
          initial={landingData || { lifecycle_stage: "applicant" }}
          onBack={() => setView(WIZARD_LANDING)}
          onSave={handleGenerate}
          loading={loading}
          error={error}
        />
      </div>
    );
  }

  return <ChatView user={user} onStartWizard={handleStartWizard} />;
}

function ChatView({ user, onStartWizard }) {
  const { messages, addMessage, isStreaming, setIsStreaming, clearMessages } = useChat();
  const location = useLocation();
  const [input, setInput] = useState("");
  const [sessionId, setSessionId] = useState(null);
  const [profile, setProfile] = useState(null);
  const scrollRef = useRef(null);
  const meta = ROLE_META[user?.role];
  const prompts = suggestedPrompts[user?.role] || [];

  useEffect(() => {
    getProfile().then(setProfile).catch(() => setProfile(null));
  }, []);

  useEffect(() => {
    const selectedSessionId = new URLSearchParams(location.search).get("session");
    let active = true;

    setSessionId(selectedSessionId);
    clearMessages();

    if (!selectedSessionId) {
      return () => {
        active = false;
      };
    }

    const loadHistory = async () => {
      try {
        const response = await getChatHistory(selectedSessionId);
        if (!active) return;

        response.turns.forEach((turn) => {
          addMessage({
            role: turn.role === "human" ? "user" : "assistant",
            content: turn.content,
            time: "",
            intent: turn.role === "ai" ? "AI chat" : undefined,
            stage: meta?.stage || "prospect",
            confidence: turn.role === "ai" ? 0.9 : undefined,
            source: turn.role === "ai" ? "AI Assistant" : undefined,
            agent: turn.role === "ai" ? agents[0] : undefined,
          });
        });
      } catch (error) {
        if (active) {
          addMessage({
            role: "assistant",
            content: error.message || "Unable to load this conversation.",
            intent: "Error",
            stage: meta?.stage || "prospect",
            confidence: 0,
            source: "System",
            agent: agents[0],
            time: "",
          });
        }
      }
    };

    loadHistory();
    return () => {
      active = false;
    };
  }, [location.search]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, isStreaming]);

  const sendMessage = async (text, prompt) => {
    const promptObj = typeof prompt === "string" ? { text: prompt } : prompt;
    const content = (text || promptObj?.text || input).trim();

    if (!content || isStreaming) return;

    addMessage({ role: "user", content, time: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) });
    setInput("");
    setIsStreaming(true);

    try {
      const response = await apiSendMessage(content, {
        session_id: sessionId,
      });
      setSessionId(response.session_id);

      const agent = agents.find((a) => a.id === response.agent_used) || agents[0];
      addMessage({
        role: "assistant",
        content: response.reply,
        intent: response.intent || "AI chat",
        stage: meta?.stage || "prospect",
        confidence: 0.9,
        source: response.agent_used || "AI Assistant",
        agent,
        time: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      });
    } catch (err) {
      addMessage({
        role: "assistant",
        content: err.message || "Chat failed. Please try again.",
        intent: "Error",
        stage: meta?.stage || "prospect",
        confidence: 0,
        source: "System",
        agent: agents[0],
        time: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      });
    } finally {
      setIsStreaming(false);
    }
  };

  return (
    <div className="flex-1 flex flex-col h-full">
      {/* Top bar */}
      <div className="flex items-center justify-between px-5 py-3 border-b border-app-subtle">
        <div className="flex items-center gap-2">
          <Sparkles size={16} className="text-brand-300" />
          <span className="font-display text-sm font-semibold text-app-primary">AI Assistant</span>
          <span className="chip border border-app-input text-app-muted ml-2">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald2-400 animate-pulseDot" />
            Online
          </span>
        </div>
        <div className="flex items-center gap-2">
          <div className="hidden md:flex items-center gap-2 rounded-lg bg-app-elevated border border-app-subtle px-3 py-1.5">
            <Search size={14} className="text-app-faint" />
            <input
              placeholder="Search conversations..."
              className="bg-transparent text-sm text-app-primary placeholder:text-app-faint focus:outline-none w-40"
            />
          </div>
          <ThemeToggle />
        </div>
      </div>

      {/* Messages */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 lg:px-8 py-6">
        {messages.length === 0 ? (
          <WelcomeView user={user} meta={meta} prompts={prompts} onPrompt={(prompt) => sendMessage(prompt.text, prompt)} onStartWizard={onStartWizard} />
        ) : (
          <div className="max-w-3xl mx-auto space-y-6">
            {messages.map((msg, i) =>
              msg.role === "user" ? (
                <UserMessage key={i} msg={msg} />
              ) : (
                <AssistantMessage key={i} msg={msg} />
              ),
            )}
            {isStreaming && <TypingIndicator />}
          </div>
        )}
      </div>

      {/* Input */}
      <div className="px-4 lg:px-8 py-4 border-t border-app-subtle">
        <div className="max-w-3xl mx-auto">
          <div className="flex items-end gap-2 rounded-2xl glass p-2">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  sendMessage();
                }
              }}
              placeholder={`Ask about ${meta?.label} lifecycle...`}
              rows={1}
              className="flex-1 bg-transparent text-sm text-app-primary placeholder:text-app-faint focus:outline-none resize-none px-3 py-2 max-h-32"
            />
            <button
              onClick={() => sendMessage()}
              disabled={!input.trim() || isStreaming}
              className="btn-primary h-9 w-9 p-0 rounded-xl flex-shrink-0"
            >
              <Send size={16} />
            </button>
          </div>
          <p className="text-center text-[11px] text-app-faint mt-2">
            AI responses are based on official NUS DFT policies and knowledge base. Verify critical decisions.
          </p>
        </div>
      </div>
    </div>
  );
}

function WelcomeView({ user, meta, prompts, onPrompt, onStartWizard }) {
  return (
    <div className="max-w-3xl mx-auto animate-fadeIn">
      {/* Hero */}
      <div className="text-center mb-8">
        <div className="inline-flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br from-brand-500/20 to-royal-600/20 border border-brand-400/20 mb-4">
          <Sparkles size={28} className="text-brand-300" />
        </div>
        <h1 className="font-display text-2xl lg:text-3xl font-bold text-app-primary">
          Hello, {user?.name?.split(" ")[0]}
        </h1>
        <p className="text-app-muted mt-1">
          I'm your MSc DFT lifecycle assistant. How can I help you today?
        </p>
        <button onClick={onStartWizard} className="btn-outline mt-4">
          <Sparkles size={14} />
          Create profile
        </button>
      </div>

      {/* Profile summary */}
      <div className="card p-4 mb-6 flex items-center gap-4">
        <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-brand-500/15 text-brand-300 font-display font-bold">
          {user?.avatar}
        </div>
        <div className="flex-1">
          <p className="font-medium text-app-primary">{user?.name}</p>
          <p className="text-sm text-app-muted">{meta?.label} · {meta?.stage} stage</p>
        </div>
        <div className="text-right">
          <p className="text-xs text-app-faint">Lifecycle progress</p>
          <p className="font-display text-lg font-bold text-app-primary">{user?.progress}%</p>
        </div>
      </div>

      {/* Suggested prompts */}
      <div>
        <p className="text-sm font-medium text-app-secondary mb-3">Suggested for you</p>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
          {prompts.map((p, i) => (
            <button
              key={i}
              onClick={() => onPrompt(p)}
              className="group flex items-center gap-3 rounded-xl p-3.5 glass-light hover:border-brand-400/30 hover:bg-brand-500/5 transition-all text-left"
            >
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-500/10 text-brand-300 flex-shrink-0">
                <Sparkles size={15} />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm text-app-primary group-hover:text-app-primary transition">{p.text}</p>
                <p className="text-[11px] text-app-faint mt-0.5">{p.intent}</p>
              </div>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

function UserMessage({ msg }) {
  return (
    <div className="flex gap-3 justify-end animate-fadeIn">
      <div className="max-w-[80%]">
        <div className="rounded-2xl rounded-tr-sm bg-brand-500 text-white px-4 py-2.5 text-sm">
          {msg.content}
        </div>
        <p className="text-[10px] text-app-faint mt-1 text-right">{msg.time}</p>
      </div>
      <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-500/15 text-brand-300 flex-shrink-0">
        <User size={16} />
      </div>
    </div>
  );
}

function AssistantMessage({ msg }) {
  const [copied, setCopied] = useState(false);
  const [feedback, setFeedback] = useState(null);

  const handleCopy = () => {
    navigator.clipboard.writeText(msg.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="flex gap-3 animate-fadeIn">
      <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-500/10 text-brand-300 flex-shrink-0">
        <Bot size={16} />
      </div>
      <div className="flex-1 min-w-0">
        <div className="card p-4">
          {/* Agent trace */}
          {msg.agent && (
            <div className="flex items-center gap-2 mb-3 pb-3 border-b border-app-subtle">
              <Network size={13} className="text-brand-300" />
              <span className="text-xs font-medium text-brand-300">{msg.agent.name}</span>
              <ChevronDown size={12} className="text-app-faint" />
              <span className="text-[11px] text-app-faint">{msg.agent.role}</span>
            </div>
          )}

          <div className="prose prose-sm prose-invert text-sm text-app-primary leading-relaxed break-words">
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{
                a: ({ node, ...props }) => {
                  const href = props.href || "";
                  if (href.startsWith("mailto:")) {
                    return (
                      <a
                        {...props}
                        href={href}
                        onClick={(e) => {
                          e.preventDefault();
                          window.location.href = href;
                        }}
                        className="text-brand-300 hover:underline"
                      />
                    );
                  }
                  return (
                    <a
                      {...props}
                      href={href}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-brand-300 hover:underline"
                    />
                  );
                },
              }}
            >
              {msg.content}
            </ReactMarkdown>
          </div>

          {/* Metadata */}
          <div className="flex flex-wrap items-center gap-2 mt-3 pt-3 border-t border-app-subtle">
            <MetaChip label="Intent" value={msg.intent} color="brand" />
            <MetaChip label="Stage" value={msg.stage} color="royal" />
            <MetaChip
              label="Confidence"
              value={`${Math.round(msg.confidence * 100)}%`}
              color={msg.confidence > 0.85 ? "emerald2" : msg.confidence > 0.6 ? "amber" : "red"}
            />
            <MetaChip label="Source" value={msg.source} color="cyan2" />
          </div>
        </div>

        {/* Actions */}
        <div className="flex items-center gap-1 mt-2">
          <button
            onClick={handleCopy}
            className="flex items-center gap-1 rounded-lg px-2 py-1 text-xs text-app-muted hover:text-app-primary hover:bg-app-hover transition"
          >
            <Copy size={12} />
            {copied ? "Copied" : "Copy"}
          </button>
          <button
            onClick={() => setFeedback("up")}
            className={cn(
              "flex items-center gap-1 rounded-lg px-2 py-1 text-xs transition",
              feedback === "up" ? "text-emerald2-400 bg-emerald2-500/10" : "text-app-muted hover:text-app-primary hover:bg-app-hover",
            )}
          >
            <ThumbsUp size={12} />
          </button>
          <button
            onClick={() => setFeedback("down")}
            className={cn(
              "flex items-center gap-1 rounded-lg px-2 py-1 text-xs transition",
              feedback === "down" ? "text-red-400 bg-red-500/10" : "text-app-muted hover:text-app-primary hover:bg-app-hover",
            )}
          >
            <ThumbsDown size={12} />
          </button>
          <button className="flex items-center gap-1 rounded-lg px-2 py-1 text-xs text-app-muted hover:text-app-primary hover:bg-app-hover transition">
            <RefreshCw size={12} />
          </button>
          <span className="text-[10px] text-app-faint ml-1">{msg.time}</span>
        </div>
      </div>
    </div>
  );
}

function MetaChip({ label, value, color }) {
  return (
    <span className="chip border bg-app-hover border-app-subtle">
      <span className="text-app-faint">{label}:</span>
      <span className={cn(
        "font-medium",
        color === "brand" && "text-brand-300",
        color === "royal" && "text-royal-300",
        color === "cyan2" && "text-cyan2-400",
        color === "emerald2" && "text-emerald2-400",
        color === "amber" && "text-amber-300",
        color === "red" && "text-red-300",
      )}>
        {value}
      </span>
    </span>
  );
}

function TypingIndicator() {
  return (
    <div className="flex gap-3 animate-fadeIn">
      <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-brand-500 to-royal-600 text-app-primary flex-shrink-0">
        <Bot size={16} />
      </div>
      <div className="card p-4 flex items-center gap-1.5">
        <span className="h-2 w-2 rounded-full bg-brand-400 animate-pulseDot" style={{ animationDelay: "0ms" }} />
        <span className="h-2 w-2 rounded-full bg-brand-400 animate-pulseDot" style={{ animationDelay: "200ms" }} />
        <span className="h-2 w-2 rounded-full bg-brand-400 animate-pulseDot" style={{ animationDelay: "400ms" }} />
        <span className="text-xs text-app-muted ml-2">Agent is thinking...</span>
      </div>
    </div>
  );
}