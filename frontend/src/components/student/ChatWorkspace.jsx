import { useState, useRef, useEffect } from "react";
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
import { suggestedPrompts, aiResponses, agents } from "../../data/conversations";
import { buildResults } from "../../data/wizard";
import { cn } from "../../utils/cn";
import ThemeToggle from "../ThemeToggle";
import LandingStep from "./wizard/LandingStep";
import FormStep from "./wizard/FormStep";
import ResultsStep from "./wizard/ResultsStep";
import SettingsModal from "./wizard/SettingsModal";

const WIZARD_LANDING = "landing";
const WIZARD_FORM = "form";
const WIZARD_RESULTS = "results";
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
  const [results, setResults] = useState(null);
  const [settingsOpen, setSettingsOpen] = useState(false);

  const handleLandingAdvance = (data) => {
    setLandingData(data);
    setView(WIZARD_FORM);
  };

  const handleGenerate = (formProfile) => {
    const fullProfile = { ...formProfile, cvName: landingData?.cvName };
    setProfile(fullProfile);
    setResults(buildResults(fullProfile));
    setView(WIZARD_RESULTS);
  };

  const handleStartChat = () => {
    clearMessages();
    const isApplicant = profile.lifecycle_stage === "applicant";
    const summary = isApplicant
      ? `I've completed the profile wizard. My background: ${profile.degree_level || "N/A"} in ${profile.field_of_study || "N/A"}, ${profile.work_years || 0} years work experience, targeting ${profile.target_roles.join(", ") || "general FinTech roles"}. Please help me with my next steps.`
      : `I'm a current student. Completed modules: ${profile.completed_modules || "none"}. Target roles: ${profile.target_roles.join(", ") || "exploring"}. Please help me plan my next steps.`;
    addMessage({ role: "user", content: summary, time: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) });
    setIsStreaming(true);
    setTimeout(() => {
      addMessage({
        role: "assistant",
        content: isApplicant
          ? "Thanks for sharing your profile! Based on your background and goals, I can help you with eligibility checks, application preparation, programme comparison, and course planning. What would you like to explore first?"
          : "Great! Based on your completed modules and career goals, I can help with course planning, skill-gap analysis, and career direction. What would you like to dive into?",
        intent: "Profile Wizard Summary",
        stage: isApplicant ? "Discover" : "Study",
        confidence: 0.95,
        source: "AI Recommendation",
        agent: agents[0],
        time: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      });
      setIsStreaming(false);
    }, 900);
    setView(CHAT);
  };

  const handleSkip = () => {
    clearMessages();
    setView(CHAT);
  };

  const handleStartWizard = () => {
    setView(WIZARD_LANDING);
  };

  const handleRegenerate = () => {
    setView(WIZARD_FORM);
  };

  if (view === WIZARD_LANDING) {
    return (
      <div className="flex-1 flex flex-col h-full overflow-y-auto">
        <LandingStep onAdvance={handleLandingAdvance} onOpenSettings={() => setSettingsOpen(true)} onSkip={handleSkip} />
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
          onGenerate={handleGenerate}
        />
      </div>
    );
  }

  if (view === WIZARD_RESULTS) {
    return (
      <div className="flex-1 flex flex-col h-full overflow-y-auto">
        <ResultsStep results={results} onBack={handleRegenerate} onStartChat={handleStartChat} />
      </div>
    );
  }

  return <ChatView user={user} onStartWizard={handleStartWizard} />;
}

function ChatView({ user, onStartWizard }) {
  const { messages, addMessage, isStreaming, setIsStreaming, clearMessages } = useChat();
  const [input, setInput] = useState("");
  const scrollRef = useRef(null);
  const meta = ROLE_META[user?.role];
  const prompts = suggestedPrompts[user?.role] || [];

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, isStreaming]);

  const findResponse = (text) => {
    const match = prompts.find((p) => p.text.toLowerCase() === text.toLowerCase());
    if (match) return aiResponses[match.intent] || aiResponses.default;
    if (/eligib/i.test(text)) return aiResponses["Eligibility Check"];
    if (/compare/i.test(text)) return aiResponses["Programme Comparison"];
    if (/career/i.test(text)) return aiResponses["Career Outcomes"];
    if (/module|curriculum|course/i.test(text)) return aiResponses["Curriculum Browse"];
    if (/status/i.test(text)) return aiResponses["Status Check"];
    if (/document|missing/i.test(text)) return aiResponses["Document Audit"];
    if (/checklist/i.test(text)) return aiResponses["Checklist Build"];
    if (/progress|graduat/i.test(text)) return aiResponses["Progress Audit"];
    if (/plan.*module|degree.*plan/i.test(text)) return aiResponses["Degree Planning"];
    return aiResponses.default;
  };

  const sendMessage = (text) => {
    const content = text || input.trim();
    if (!content || isStreaming) return;

    addMessage({ role: "user", content, time: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) });
    setInput("");

    setIsStreaming(true);
    const response = findResponse(content);
    const agent = agents.find((a) => a.id === response.agent) || agents[0];

    setTimeout(() => {
      addMessage({
        role: "assistant",
        content: response.text,
        intent: response.intent,
        stage: response.stage,
        confidence: response.confidence,
        source: response.source,
        agent,
        time: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      });
      setIsStreaming(false);
    }, 900);
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
          <WelcomeView user={user} meta={meta} prompts={prompts} onPrompt={sendMessage} onStartWizard={onStartWizard} />
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
          Start profile wizard
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
              onClick={() => onPrompt(p.text)}
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
        <div className="rounded-2xl rounded-tr-sm bg-brand-500 text-app-primary px-4 py-2.5 text-sm">
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
      <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-brand-500 to-royal-600 text-app-primary flex-shrink-0">
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

          <p className="text-sm text-app-primary whitespace-pre-wrap leading-relaxed">{msg.content}</p>

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