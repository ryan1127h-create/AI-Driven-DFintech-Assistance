import { useState, useRef, useEffect } from "react";
import { createPortal } from "react-dom";
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
  BookOpen,
  ExternalLink,
} from "lucide-react";
import { useRole } from "../../context/RoleContext";
import { useChat } from "../../context/ChatContext";
import { ROLE_META } from "../../data/roles";
import { suggestedPrompts, resolveAgent } from "../../data/chat";
import {
  getChatHistory,
  sendMessageStream,
  rollbackChat,
} from "../../../api";
import { cn } from "../../utils/cn";
import { formatTime } from "../../utils/format";
import OnboardingFlow from "./onboarding/OnboardingFlow";
import ConsentCard from "./chat/ConsentCard";
import QuickFillCard from "./chat/QuickFillCard";
import SaveSuggestions from "./chat/SaveSuggestions";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

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
  const location = useLocation();
  // The profile page's "Update from CV" lands here with this state, opening
  // profile setup straight on the CV step.
  const [cvImportOpen, setCvImportOpen] = useState(Boolean(location.state?.openCvImport));
  // Settings' "Run it again" lands here with this state.
  const [onboardingOpen, setOnboardingOpen] = useState(Boolean(location.state?.openOnboarding));
  // Also when that happens while this page is already open.
  useEffect(() => {
    if (location.state?.openOnboarding) setOnboardingOpen(true);
  }, [location.state]);

  const closeOnboarding = () => {
    setOnboardingOpen(false);
    if (cvImportOpen || location.state) {
      setCvImportOpen(false);
      navigate("/app", { replace: true, state: null });
    }
  };

  if (user?.onboardingStatus === "not_started" || onboardingOpen || cvImportOpen) {
    return <OnboardingFlow onDone={closeOnboarding} initialPhase={cvImportOpen ? "cv" : "entry"} />;
  }

  // Once the questionnaire is done the profile page is where answers change;
  // until then the same button reopens the questionnaire.
  const profileDone = user?.onboardingStatus === "completed";
  const openProfile = () => (profileDone ? navigate("/workspace/profile") : setOnboardingOpen(true));
  return <ChatView user={user} profileDone={profileDone} onOpenProfile={openProfile} />;
}

function ProfileReminder({ onOpen }) {
  return (
    <div className="mx-4 lg:mx-8 mt-3 flex items-center justify-between gap-3 rounded-lg border border-brand-400/20 bg-brand-500/10 px-4 py-2.5 text-sm">
      <span className="text-app-secondary">Add a few details to get advice that fits you.</span>
      <button type="button" onClick={onOpen} className="font-medium text-brand-300 hover:underline">
        Set up profile
      </button>
    </div>
  );
}

function ChatView({ user, profileDone, onOpenProfile }) {
  const {
    messages, addMessage, updateLastMessage, removeLastMessages, isStreaming, setIsStreaming, clearMessages,
    conversationsChanged,
  } = useChat();
  const location = useLocation();
  const [input, setInput] = useState("");
  const [sessionId, setSessionId] = useState(null);
  const scrollRef = useRef(null);
  const inputRef = useRef(null);
  // Card fields dismissed since the last message was sent; they go out
  // with the next one, so the backend stops offering them this session.
  const pendingDeclines = useRef([]);
  const meta = ROLE_META[user?.role];
  const prompts = suggestedPrompts[user?.role] || [];

  useEffect(() => {
    const selectedSessionId = new URLSearchParams(location.search).get("session");
    let active = true;

    setSessionId(selectedSessionId);
    clearMessages();
    pendingDeclines.current = [];

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
            agent: isAi ? resolveAgent(turn.agent_used) : undefined,
            sources: isAi ? turn.sources || [] : undefined,
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
            agent: resolveAgent(null),
            time: "",
          });
        }
      }
    };

    loadHistory();
    return () => {
      active = false;
    };
    // location.key, not only the search: "New Chat" from a conversation
    // that was started here (its URL is still plain /app) navigates to the
    // same URL, and only the key tells the two apart — without it the old
    // session id survived and the next message continued that conversation.
  }, [location.search, location.key]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, isStreaming]);

  const timeNow = () => formatTime(new Date());

  // declinedFields: card fields the user skipped to get this answer.
  const sendMessage = async (text, prompt, declinedFields = []) => {
    const promptObj = typeof prompt === "string" ? { text: prompt } : prompt;
    const content = (text || promptObj?.text || input).trim();

    if (!content || isStreaming) return;
    const declined = [...new Set([...pendingDeclines.current, ...declinedFields])];
    pendingDeclines.current = [];

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
        agent: resolveAgent(null),
      }));
    };

    try {
      await sendMessageStream(content, { session_id: sessionId, declined_fields: declined }, {
        onStep: (event) => {
          updateLastMessage((m) => ({ ...m, steps: [...(m.steps || []), event] }));
        },
        onToken: (text) => {
          updateLastMessage((m) => ({ ...m, content: (m.content || "") + text }));
        },
        onDone: (data) => {
          setSessionId(data.session_id);
          conversationsChanged();
          const agent = resolveAgent(data.agent_used);
          updateLastMessage((m) => {
            const classified = (m.steps || []).find((s) => s.stage === "classified");
            return {
              ...m,
              // Snap to the authoritative final text (includes the Sources
              // footer, appended server-side only after streaming ends —
              // see agents/supervisor.py/rag_agent.py).
              content: data.reply,
              streaming: false,
              card: data.card || null,
              supplementCard: data.supplement_card || null,
              saveSuggestions: data.save_suggestions || [],
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
      </div>

      {user?.onboardingStatus === "skipped" && <ProfileReminder onOpen={onOpenProfile} />}

      {/* Messages */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 lg:px-8 py-6">
        {messages.length === 0 ? (
          <WelcomeView user={user} prompts={prompts} onPrompt={(prompt) => sendMessage(prompt.text, prompt)} onOpenProfile={onOpenProfile} profileDone={profileDone} />
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
                  cardActive={i === messages.length - 1 && !isStreaming}
                  onCardAnswered={() => sendMessage(messages[i - 1]?.content)}
                  onCardSkipped={(fields) => sendMessage(messages[i - 1]?.content, null, fields)}
                  onCardDismissed={(fields) => {
                    pendingDeclines.current = [...pendingDeclines.current, ...fields];
                  }}
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

function WelcomeView({ user, prompts, onPrompt, onOpenProfile, profileDone }) {
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
        <button onClick={onOpenProfile} className="btn-outline mt-4">
          {profileDone ? <Pencil size={14} /> : <Sparkles size={14} />}
          {profileDone ? "Edit profile" : "Set up profile"}
        </button>
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

function AssistantMessage({
  msg, rollbackTurns, rollbackPrefill, onRollback, cardActive, onCardAnswered, onCardSkipped, onCardDismissed,
}) {
  const [copied, setCopied] = useState(false);
  // A live reply carries its sources inside its text; one loaded from
  // history has them alongside.
  const { body, sources: inText } = splitSources(msg.content);
  const sources = msg.sources?.length ? msg.sources : inText;

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

          {body && (
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
                {body}
              </ReactMarkdown>
              {msg.streaming && <span className="inline-block w-1.5 h-4 bg-brand-300 ml-0.5 align-middle animate-pulseDot" />}
            </div>
          )}

          {/* What the reply needs before it can answer, answerable in place */}
          {msg.card?.kind === "quick_fill" && (
            <QuickFillCard card={msg.card} active={cardActive} onAnswered={onCardAnswered} onSkip={onCardSkipped} />
          )}
          {msg.card?.kind === "consent" && (
            <ConsentCard card={msg.card} active={cardActive} onAnswered={onCardAnswered} />
          )}

          {/* Details that would sharpen the answer, never in the way */}
          {msg.supplementCard && (
            <QuickFillCard
              card={msg.supplementCard}
              active={cardActive}
              onAnswered={onCardAnswered}
              onDismiss={onCardDismissed}
            />
          )}

          {msg.saveSuggestions?.length > 0 && <SaveSuggestions suggestions={msg.saveSuggestions} />}

          {/* Metadata — only meaningful once the reply has fully resolved */}
          {!msg.streaming && (
            <div className="flex flex-wrap items-center gap-2 mt-3 pt-3 border-t border-app-subtle">
              <MetaChip label="Intent" value={msg.intent} color="brand" />
              <MetaChip label="Stage" value={msg.stage} color="royal" />
              <MetaChip label="Agent" value={msg.source} color="cyan2" />
              {sources.length > 0 && <SourcesChip sources={sources} />}
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

// The backend appends a reply's sources as a trailing "Sources:" list (see
// orchestrator/dispatch/__init__.py::_reply_with_sources); the chat shows
// them in the Sources chip instead of the message body. Copy keeps the full
// text.
const SOURCES_BLOCK = /\n+Sources:\n((?:[ \t]*- .*(?:\n|$))+)\s*$/;

function splitSources(content) {
  const match = (content || "").match(SOURCES_BLOCK);
  if (!match) return { body: content, sources: [] };
  const sources = match[1].split("\n").map((line) => line.replace(/^\s*-\s*/, "").trim()).filter(Boolean);
  return { body: content.slice(0, match.index).trimEnd(), sources };
}

const POPOVER_WIDTH = 320;
const POPOVER_MARGIN = 12;

// The list opens above the chip in a portal on <body>, positioned from the
// chip and the window, so it never widens the chat column (no horizontal
// scrollbar) and shifts left when the chip sits near the right edge. It is
// only rendered while open; scrolling or resizing closes it.
function SourcesChip({ sources }) {
  const chipRef = useRef(null);
  const closeTimer = useRef(null);
  const [position, setPosition] = useState(null);

  const open = () => {
    clearTimeout(closeTimer.current);
    const rect = chipRef.current?.getBoundingClientRect();
    if (!rect) return;
    const width = Math.min(POPOVER_WIDTH, window.innerWidth - POPOVER_MARGIN * 2);
    const left = Math.min(Math.max(rect.left, POPOVER_MARGIN), window.innerWidth - width - POPOVER_MARGIN);
    setPosition({ left, width, bottom: window.innerHeight - rect.top + 6 });
  };
  // A short delay lets the pointer travel from the chip onto the list.
  const scheduleClose = () => {
    clearTimeout(closeTimer.current);
    closeTimer.current = setTimeout(() => setPosition(null), 120);
  };

  useEffect(() => {
    if (!position) return undefined;
    const close = () => setPosition(null);
    window.addEventListener("scroll", close, true);
    window.addEventListener("resize", close);
    return () => {
      window.removeEventListener("scroll", close, true);
      window.removeEventListener("resize", close);
    };
  }, [position]);

  useEffect(() => () => clearTimeout(closeTimer.current), []);

  return (
    <>
      <span
        ref={chipRef}
        tabIndex={0}
        onMouseEnter={open}
        onMouseLeave={scheduleClose}
        onFocus={open}
        onBlur={scheduleClose}
        className={cn(
          "chip cursor-default border bg-app-hover transition",
          position ? "border-brand-400/30" : "border-app-subtle",
        )}
      >
        <BookOpen size={11} className="text-app-faint" />
        <span className="text-app-faint">Sources</span>
        <span className="font-medium text-app-secondary">{sources.length}</span>
      </span>
      {position &&
        createPortal(
          <div
            role="tooltip"
            onMouseEnter={open}
            onMouseLeave={scheduleClose}
            style={{ position: "fixed", left: position.left, bottom: position.bottom, width: position.width }}
            className="z-50 rounded-xl border border-app-subtle p-3 shadow-glass glass animate-fadeIn"
          >
            <p className="mb-1.5 text-[11px] font-medium uppercase tracking-wide text-app-faint">Sources</p>
            <ul className="space-y-1.5">
              {sources.map((source) => (
                <li key={source} className="flex items-start gap-1.5 text-xs">
                  <ExternalLink size={11} className="mt-0.5 flex-shrink-0 text-app-faint" />
                  {/^https?:\/\//.test(source) ? (
                    <a href={source} target="_blank" rel="noopener noreferrer" className="min-w-0 break-all text-brand-300 hover:underline">
                      {source}
                    </a>
                  ) : (
                    <span className="min-w-0 break-words text-app-secondary">{source}</span>
                  )}
                </li>
              ))}
            </ul>
          </div>,
          document.body,
        )}
    </>
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
  waiting_for_history: () => "Tidying up the earlier conversation — sending in a moment",
  answering: (e) => `Generating the answer${e.agent ? ` (${e.agent})` : ""}`,
  evaluating: () => "Checking the answer actually covers your question",
  revising: () => "Answer needed more — refining it",
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