import { useState, useRef, useEffect } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import {
  Send,
  Sparkles,
  Copy,
  ChevronDown,
  ChevronRight,
  Network,
  Bot,
  User,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  Undo2,
  Loader2,
  Pencil,
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
  sendMessageStream,
  rollbackChat,
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

// How many of the most recent AI replies get a rollback ("go back to before
// this point") button. This is a UI display cap, not a safety boundary — the
// real boundary is each message's `archived` flag (an archived turn, and
// everything before it, can never be rolled back — see
// backend/app/orchestrator/turn_service.py::rollback_conversation) plus
// the backend's own validation on every request regardless of what the UI
// sends.
const MAX_ROLLBACK_TURNS = 5;

// Walks `messages` from the end, pairing up the most recent AI replies with
// how many turns rolling back to "before" them would remove — without
// needing to track each message's absolute turn number. Stops at the first
// archived reply (archived turns are always the oldest — see above) or once
// MAX_ROLLBACK_TURNS replies have been found, whichever comes first.
// Returns a Map of message-array-index -> turnsToRemove.
function computeRollbackEligibility(messages) {
  const eligible = new Map();
  let turnsBack = 0;
  for (let i = messages.length - 1; i >= 0; i--) {
    const msg = messages[i];
    if (msg.role !== "assistant" || msg.streaming) continue;
    if (msg.archived) break;
    turnsBack += 1;
    eligible.set(i, turnsBack);
    if (turnsBack >= MAX_ROLLBACK_TURNS) break;
  }
  return eligible;
}

export default function ChatWorkspace() {
  const { user } = useRole();
  const navigate = useNavigate();
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
      // Already has a profile — send them to the real editing page instead
      // of just re-affirming the CHAT view they're already in (see
      // StudentSidebar.jsx's own "Profile" quick-access link, same target).
      navigate("/workspace/profile");
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
  const { messages, addMessage, updateLastMessage, removeLastMessages, isStreaming, setIsStreaming, clearMessages } = useChat();
  const location = useLocation();
  const [input, setInput] = useState("");
  const [sessionId, setSessionId] = useState(null);
  const [profile, setProfile] = useState(null);
  const scrollRef = useRef(null);
  const inputRef = useRef(null);
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
          const isAi = turn.role === "ai";
          addMessage({
            role: isAi ? "assistant" : "user",
            content: turn.content,
            time: "",
            // turn.intents/turn.agent_used come from student.messages.turn_intents
            // (archived turns) or conversations.pending_turn_intents (not yet
            // archived) — see service.py::_pair_to_turns. Absent only for turns
            // logged before this field existed, in which case fall back to a
            // generic label rather than showing nothing.
            intent: isAi ? (turn.intents?.join(", ") || "AI chat") : undefined,
            stage: meta?.stage || "prospect",
            source: isAi ? (turn.agent_used || "AI Assistant") : undefined,
            agent: isAi ? (agents.find((a) => a.id === turn.agent_used) || agents[0]) : undefined,
            // Frozen/archived turns can never be rolled back (see
            // backend/app/orchestrator/turn_service.py::rollback_conversation)
            // — drives whether this message is eligible for the rollback button.
            archived: turn.archived,
          });
        });
      } catch (error) {
        if (active) {
          addMessage({
            role: "assistant",
            content: error.message || "Unable to load this conversation.",
            intent: "Error",
            stage: meta?.stage || "prospect",
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

  const timeNow = () => new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

  const sendMessage = async (text, prompt) => {
    const promptObj = typeof prompt === "string" ? { text: prompt } : prompt;
    const content = (text || promptObj?.text || input).trim();

    if (!content || isStreaming) return;

    addMessage({ role: "user", content, time: timeNow() });
    setInput("");
    setIsStreaming(true);
    // Placeholder assistant message — filled in live as "step"/"token" events
    // arrive (see AgentTraceTimeline below), replacing the old static
    // TypingIndicator with a real path-of-processing display.
    addMessage({
      role: "assistant",
      content: "",
      steps: [],
      streaming: true,
      stage: meta?.stage || "prospect",
      time: timeNow(),
    });

    const finalizeAsError = (message) => {
      updateLastMessage((m) => ({
        ...m,
        streaming: false,
        content: m.content || message || "Chat failed. Please try again.",
        intent: "Error",
        source: "System",
        agent: agents[0],
      }));
    };

    try {
      await sendMessageStream(content, { session_id: sessionId }, {
        onStep: (event) => {
          updateLastMessage((m) => ({ ...m, steps: [...(m.steps || []), event] }));
        },
        onToken: (text) => {
          updateLastMessage((m) => ({ ...m, content: (m.content || "") + text }));
        },
        onDone: (data) => {
          setSessionId(data.session_id);
          const agent = agents.find((a) => a.id === data.agent_used) || agents[0];
          updateLastMessage((m) => {
            const classified = (m.steps || []).find((s) => s.stage === "classified");
            return {
              ...m,
              // Snap to the authoritative final text (includes the Sources
              // footer, appended server-side only after streaming ends —
              // see agents/supervisor.py/rag_agent.py).
              content: data.reply,
              streaming: false,
              intent: classified?.intents?.join(", ") || "AI chat",
              source: data.agent_used || "AI Assistant",
              agent,
            };
          });
        },
        onError: (data) => finalizeAsError(data.detail),
      });
    } catch (err) {
      finalizeAsError(err.message);
    } finally {
      setIsStreaming(false);
    }
  };

  const handleRollback = async (turnsToRemove, originalUserMessage) => {
    if (!sessionId || isStreaming) return;
    if (!window.confirm(`Go back to before this point? The last ${turnsToRemove} turn${turnsToRemove > 1 ? "s" : ""} of this conversation will be permanently deleted and cannot be recovered.`)) return;

    try {
      await rollbackChat(sessionId, turnsToRemove);
      // Each turn is exactly one user message + one AI message (same
      // pairing assumption the backend relies on — see
      // service.py::_pair_to_turns).
      removeLastMessages(turnsToRemove * 2);
      // Refill the input with the question that started the rolled-back
      // turn, so the user can tweak and resend it rather than retyping.
      setInput(originalUserMessage || "");
      inputRef.current?.focus();
    } catch (err) {
      alert(err.message || "Failed to roll back. Please try again.");
    }
  };

  const rollbackEligibility = computeRollbackEligibility(messages);

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
          <ThemeToggle />
        </div>
      </div>

      {/* Messages */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 lg:px-8 py-6">
        {messages.length === 0 ? (
          <WelcomeView user={user} meta={meta} prompts={prompts} onPrompt={(prompt) => sendMessage(prompt.text, prompt)} onStartWizard={onStartWizard} hasProfile={!!profile} />
        ) : (
          <div className="max-w-3xl mx-auto space-y-6">
            {messages.map((msg, i) =>
              msg.role === "user" ? (
                <UserMessage key={i} msg={msg} />
              ) : (
                <AssistantMessage
                  key={i}
                  msg={msg}
                  rollbackTurns={rollbackEligibility.get(i)}
                  rollbackPrefill={messages[i - 1]?.content}
                  onRollback={handleRollback}
                />
              ),
            )}
          </div>
        )}
      </div>

      {/* Input */}
      <div className="px-4 lg:px-8 py-4 border-t border-app-subtle">
        <div className="max-w-3xl mx-auto">
          <div className="flex items-end gap-2 rounded-2xl glass p-2">
            <textarea
              ref={inputRef}
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

function WelcomeView({ user, meta, prompts, onPrompt, onStartWizard, hasProfile }) {
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
          {hasProfile ? <Pencil size={14} /> : <Sparkles size={14} />}
          {hasProfile ? "Edit profile" : "Create profile"}
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

function AssistantMessage({ msg, rollbackTurns, rollbackPrefill, onRollback }) {
  const [copied, setCopied] = useState(false);

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
        <div className="card p-4 relative">
          {rollbackTurns !== undefined && (
            <button
              onClick={() => onRollback(rollbackTurns, rollbackPrefill)}
              title="Go back to before this point"
              className="absolute right-2 top-2 flex h-6 w-6 items-center justify-center rounded-lg text-app-faint hover:text-app-primary hover:bg-app-hover transition"
            >
              <Undo2 size={13} />
            </button>
          )}
          {/* Agent trace (final, once the reply is resolved) */}
          {msg.agent && (
            <div className="flex items-center gap-2 mb-3 pb-3 border-b border-app-subtle">
              <Network size={13} className="text-brand-300" />
              <span className="text-xs font-medium text-brand-300">{msg.agent.name}</span>
              <ChevronDown size={12} className="text-app-faint" />
              <span className="text-[11px] text-app-faint">{msg.agent.role}</span>
            </div>
          )}

          {/* Live "thinking path" while the reply streams in */}
          {msg.steps?.length > 0 && (
            <AgentTraceTimeline steps={msg.steps} expanded={msg.streaming} />
          )}

          {msg.streaming && !msg.steps?.length && !msg.content && <ThinkingDots />}

          {msg.content && (
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
              {msg.streaming && <span className="inline-block w-1.5 h-4 bg-brand-300 ml-0.5 align-middle animate-pulseDot" />}
            </div>
          )}

          {/* Metadata — only meaningful once the reply has fully resolved */}
          {!msg.streaming && (
            <div className="flex flex-wrap items-center gap-2 mt-3 pt-3 border-t border-app-subtle">
              <MetaChip label="Intent" value={msg.intent} color="brand" />
              <MetaChip label="Stage" value={msg.stage} color="royal" />
              <MetaChip label="Source" value={msg.source} color="cyan2" />
            </div>
          )}
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

// Momentary placeholder shown before the first "step" event has arrived yet
// (connection just opened, nothing to report as a path step).
function ThinkingDots() {
  return (
    <div className="flex items-center gap-1.5 py-1">
      <span className="h-2 w-2 rounded-full bg-brand-400 animate-pulseDot" style={{ animationDelay: "0ms" }} />
      <span className="h-2 w-2 rounded-full bg-brand-400 animate-pulseDot" style={{ animationDelay: "200ms" }} />
      <span className="h-2 w-2 rounded-full bg-brand-400 animate-pulseDot" style={{ animationDelay: "400ms" }} />
      <span className="text-xs text-app-muted ml-2">Thinking...</span>
    </div>
  );
}

// One entry per {"type":"step", "stage": ..., ...} event from POST
// /chat/stream (see agents/supervisor.py / rag_agent.py / etc. on the
// backend for exactly when each stage fires). Renders the "path" the agent
// took — expanded while the reply is still streaming in, collapsible into a
// small toggle once it's done (mirrors Claude's collapsed "Thinking" panel).
const STEP_LABELS = {
  classifying: () => "Understanding your question",
  classified: (e) => `Classified as: ${(e.intents || []).join(", ") || "general"}`,
  dispatch_start: (e) => `Multiple topics detected — processing in parallel: ${(e.agents || []).join(", ")}`,
  branch_done: (e) => `${e.agent} ${e.timeout ? "timed out" : e.ok ? "finished" : "failed"}`,
  synthesizing: () => "Combining the answers into one reply",
  answering: (e) => `Generating the answer${e.agent ? ` (${e.agent})` : ""}`,
};

// `active` = this is the step currently being worked on (the last one, while
// the reply is still streaming) — gets a spinner instead of a static dot.
// branch_done steps are always a settled outcome (ok/failed/timed out), so
// they never spin regardless of position.
function stepIcon(step, active) {
  if (step.stage === "branch_done") {
    if (step.timeout) return <AlertTriangle size={13} className="text-amber-400" />;
    return step.ok ? <CheckCircle2 size={13} className="text-emerald2-400" /> : <XCircle size={13} className="text-red-400" />;
  }
  if (active) {
    return <Loader2 size={14} className="text-brand-400 animate-spin" />;
  }
  return <span className="h-1.5 w-1.5 rounded-full bg-brand-400" />;
}

function AgentTraceTimeline({ steps, expanded }) {
  const [open, setOpen] = useState(true);
  const isOpen = expanded || open;

  return (
    <div className="mb-3 pb-3 border-b border-app-subtle">
      {!expanded && (
        <button
          onClick={() => setOpen((v) => !v)}
          className="flex items-center gap-1 text-[11px] text-app-faint hover:text-app-muted transition mb-1.5"
        >
          {open ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
          View processing steps ({steps.length})
        </button>
      )}
      {isOpen && (
        <div className="space-y-2">
          {steps.map((step, i) => {
            // Still-streaming + last in the list + not already a settled
            // outcome = the step actually in progress right now.
            const isActive = expanded && i === steps.length - 1 && step.stage !== "branch_done";
            return (
              <div
                key={i}
                className={cn(
                  "flex items-center gap-2 animate-fadeIn transition-all duration-300 ease-out",
                  isActive ? "text-sm font-medium text-app-primary" : "text-xs text-app-muted",
                )}
              >
                <span className="flex-shrink-0 flex items-center justify-center w-3.5 h-3.5 transition-transform duration-300">
                  {stepIcon(step, isActive)}
                </span>
                <span className="transition-colors duration-300">{STEP_LABELS[step.stage]?.(step) || step.stage}</span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}