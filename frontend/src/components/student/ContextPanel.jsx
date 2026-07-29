import { useNavigate } from "react-router-dom";
import {
  Sparkles,
  TrendingUp,
  AlertCircle,
  CheckCircle2,
  Clock,
  ArrowRight,
  Lightbulb,
  Activity,
  Circle,
  GitCompare,
  BookOpen,
  Map,
  CalendarPlus,
  Home,
  Users,
  Calendar,
  HandHeart,
  FileText,
  DollarSign,
  Briefcase,
  Network,
} from "lucide-react";
import { useRole } from "../../context/RoleContext";
import { ROLE_META, ROLES } from "../../data/roles";
import { Badge, ProgressBar } from "../ui";
import { recommendedActions, aiInsights, workflowSteps } from "../../data/conversations";
import { useChat } from "../../context/ChatContext";
import { cn } from "../../utils/cn";

const actionIcons = {
  CheckCircle2, GitCompare, BookOpen, TrendingUp, ArrowRight, AlertCircle,
  Clock, Lightbulb, CalendarPlus, Home, Users, Calendar, HandHeart, FileText,
  Map, DollarSign, Briefcase, Network,
};

export default function ContextPanel() {
  const { user } = useRole();
  const meta = ROLE_META[user?.role];

  return (
    <div className="w-full h-full flex flex-col overflow-y-auto glass">
      <div className="px-4 py-4 border-b border-app-subtle">
        <div className="flex items-center gap-2">
          <Activity size={15} className="text-brand-300" />
          <h3 className="font-display text-sm font-semibold text-app-primary">Context</h3>
        </div>
        <p className="text-xs text-app-muted mt-0.5">{meta?.label} · {meta?.stage} stage</p>
      </div>

      <div className="flex-1 px-4 py-4 space-y-4">
        <LifecycleProgress user={user} />
        <RecommendedActions role={user?.role} />
        <AIInsights role={user?.role} />
        <WorkflowStatus role={user?.role} />
      </div>
    </div>
  );
}

function LifecycleProgress({ user }) {
  const stages = ["Discover", "Apply", "Enroll", "Study", "Graduate", "Alumni"];
  const meta = ROLE_META[user?.role];
  const currentIdx = stages.indexOf(meta?.stage);

  return (
    <div className="card p-4">
      <p className="text-xs font-semibold uppercase tracking-wider text-app-faint mb-3">
        Lifecycle Progress
      </p>
      <div className="flex items-center justify-between mb-2">
        <span className="font-display text-2xl font-bold text-app-primary">{user?.progress}%</span>
        <Badge color="brand">{meta?.stage}</Badge>
      </div>
      <ProgressBar value={user?.progress || 0} color="brand" />
      <div className="mt-4 space-y-1.5">
        {stages.map((s, i) => (
          <div key={s} className="flex items-center gap-2">
            <div className={`h-1.5 w-1.5 rounded-full ${i <= currentIdx ? "bg-brand-400" : "bg-app-hover"}`} />
            <span className={`text-xs ${i <= currentIdx ? "text-app-primary" : "text-app-faint"}`}>{s}</span>
            {i === currentIdx && <span className="text-[10px] text-brand-300 ml-auto">current</span>}
          </div>
        ))}
      </div>
    </div>
  );
}

function RecommendedActions({ role }) {
  const navigate = useNavigate();
  const { addMessage, setIsStreaming } = useChat();
  const list = recommendedActions[role] || recommendedActions[ROLES.PROSPECTIVE];

  const handleAction = (action) => {
    if (action.prompt) {
      addMessage({ role: "user", content: action.prompt, time: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) });
      setIsStreaming(true);
      navigate("/app");
    } else if (action.route) {
      navigate(action.route);
    }
  };

  return (
    <div className="card p-4">
      <p className="text-xs font-semibold uppercase tracking-wider text-app-faint mb-3">
        Recommended Actions
      </p>
      <div className="space-y-2">
        {list.map((a, i) => {
          const Icon = actionIcons[a.icon] || ArrowRight;
          return (
            <button
              key={i}
              onClick={() => handleAction(a)}
              className="w-full flex items-center gap-3 rounded-lg p-2.5 bg-app-hover hover:bg-app-hover border border-app-soft hover:border-brand-400/20 transition text-left group"
            >
              <Icon size={15} className={`flex-shrink-0 ${a.color}`} />
              <span className="text-sm text-app-primary flex-1">{a.text}</span>
              {a.urgent && <span className="h-1.5 w-1.5 rounded-full bg-amber-400 animate-pulseDot" />}
              <ArrowRight size={12} className="text-app-faint group-hover:text-brand-300 transition" />
            </button>
          );
        })}
      </div>
    </div>
  );
}

function AIInsights({ role }) {
  const list = aiInsights[role] || aiInsights[ROLES.PROSPECTIVE];

  const confidenceColor = (c) =>
    c >= 0.9 ? "text-emerald2-400" : c >= 0.8 ? "text-brand-300" : "text-amber-300";

  return (
    <div className="card p-4">
      <div className="flex items-center gap-2 mb-3">
        <Sparkles size={14} className="text-brand-300" />
        <p className="text-xs font-semibold uppercase tracking-wider text-app-faint">AI Insights</p>
      </div>
      <div className="space-y-2.5">
        {list.map((ins, i) => (
          <div key={i} className="rounded-lg p-3 bg-brand-500/5 border border-brand-400/10">
            <div className="flex items-center gap-2 mb-1.5">
              <span className="chip bg-brand-500/15 text-brand-300 text-[10px] font-medium">{ins.type}</span>
              <span className={cn("text-[10px] font-medium", confidenceColor(ins.confidence))}>
                {Math.round(ins.confidence * 100)}% confidence
              </span>
            </div>
            <p className="text-sm text-app-primary leading-relaxed">{ins.text}</p>
            <div className="flex items-start gap-1.5 mt-2 pt-2 border-t border-brand-400/10">
              <Lightbulb size={11} className="text-app-faint flex-shrink-0 mt-0.5" />
              <span className="text-[11px] text-app-muted leading-relaxed">{ins.reason}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function WorkflowStatus({ role }) {
  const wf = workflowSteps[role] || workflowSteps[ROLES.PROSPECTIVE];

  const statusIcon = (status) => {
    if (status === "completed") return <CheckCircle2 size={14} className="text-emerald2-400 flex-shrink-0" />;
    if (status === "current") return <div className="h-3.5 w-3.5 rounded-full bg-brand-500 flex-shrink-0 ring-2 ring-brand-400/30 animate-pulseDot" />;
    return <Circle size={14} className="text-app-faint flex-shrink-0" />;
  };

  return (
    <div className="card p-4">
      <p className="text-xs font-semibold uppercase tracking-wider text-app-faint mb-3">
        Current Workflow
      </p>
      <div className="space-y-2.5">
        {wf.steps.map((step, i) => (
          <div key={i} className="flex items-center gap-2.5">
            {statusIcon(step.status)}
            <span className={cn(
              "text-sm flex-1",
              step.status === "completed" ? "text-app-muted line-through" :
              step.status === "current" ? "text-app-primary font-medium" :
              "text-app-faint",
            )}>
              {step.name}
            </span>
            {step.status === "current" && <Badge color="brand">Current</Badge>}
          </div>
        ))}
      </div>
      <div className="mt-3 pt-3 border-t border-app-subtle">
        <div className="flex items-start gap-2">
          <ArrowRight size={13} className="text-brand-300 flex-shrink-0 mt-0.5" />
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-wider text-app-faint">Next Action</p>
            <p className="text-sm text-app-secondary mt-0.5">{wf.nextAction}</p>
          </div>
        </div>
      </div>
    </div>
  );
}
