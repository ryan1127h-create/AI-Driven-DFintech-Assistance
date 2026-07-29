import { useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Lightbulb, ListChecks, CheckCircle, FileText,
  CheckCircle2, Clock, ArrowRight, ChevronDown, Sparkles, HelpCircle,
} from "lucide-react";
import { applicationTimeline, applicationRequirements, guidedPreparation, applicationFAQs } from "../../../data/mock";
import { PageHeader, StatusBadge } from "../PageParts";
import { Card, Badge } from "../../ui";
import { useChat } from "../../../context/ChatContext";
import { cn } from "../../../utils/cn";

export function GuidancePage() {
  const navigate = useNavigate();
  const { addMessage, setIsStreaming } = useChat();
  const [openFaq, setOpenFaq] = useState(null);

  const handlePrepAction = (prep) => {
    if (prep.prompt) {
      addMessage({ role: "user", content: prep.prompt, time: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) });
      setIsStreaming(true);
      navigate("/app");
    }
  };

  const prepIcons = { ListChecks, CheckCircle, FileText, Lightbulb };

  const timelineStatus = {
    completed: { icon: CheckCircle2, color: "text-emerald2-400", bg: "bg-emerald2-500" },
    current: { icon: Clock, color: "text-brand-300", bg: "bg-brand-500" },
    upcoming: { icon: Clock, color: "text-app-faint", bg: "bg-app-hover" },
  };

  return (
    <div>
      <PageHeader icon={Lightbulb} title="Application Guidance" subtitle="Complete guidance for your MSc DFT application" />

      {/* Application Timeline */}
      <Card className="mb-4">
        <h3 className="font-display text-base font-semibold text-app-primary mb-4">Application Timeline</h3>
        <div className="space-y-3">
          {applicationTimeline.map((t, i) => {
            const st = timelineStatus[t.status];
            const TIcon = st.icon;
            return (
              <div key={i} className="flex items-start gap-3">
                <div className="flex flex-col items-center">
                  <div className={`flex h-8 w-8 items-center justify-center rounded-full ${st.bg} text-app-primary flex-shrink-0`}>
                    <TIcon size={15} />
                  </div>
                  {i < applicationTimeline.length - 1 && (
                    <div className={`w-0.5 h-6 ${t.status === "completed" ? "bg-emerald2-500/40" : "bg-app-hover"}`} />
                  )}
                </div>
                <div className="flex-1 pb-2">
                  <div className="flex items-center gap-2">
                    <p className="text-sm font-medium text-app-primary">{t.phase}</p>
                    {t.status === "current" && <Badge color="brand">In Progress</Badge>}
                  </div>
                  <p className="text-xs text-app-muted mt-0.5">{t.date}</p>
                  <p className="text-xs text-app-faint mt-1">{t.desc}</p>
                </div>
              </div>
            );
          })}
        </div>
      </Card>

      {/* Requirements Section */}
      <Card className="mb-4">
        <h3 className="font-display text-base font-semibold text-app-primary mb-4">Requirements</h3>
        <div className="space-y-3">
          {applicationRequirements.map((req, i) => (
            <div key={i} className="rounded-lg p-3 bg-app-hover border border-app-soft">
              <div className="flex items-center justify-between mb-2">
                <p className="text-sm font-medium text-app-primary">{req.category}</p>
                <StatusBadge status={req.status} />
              </div>
              <ul className="space-y-1">
                {req.items.map((item, j) => (
                  <li key={j} className="flex items-center gap-2 text-xs text-app-muted">
                    <CheckCircle size={12} className={req.status === "verified" ? "text-emerald2-400" : "text-app-faint"} />
                    {item}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </Card>

      {/* Guided Preparation */}
      <div className="mb-4">
        <div className="flex items-center gap-2 mb-3">
          <Sparkles size={15} className="text-brand-300" />
          <h3 className="font-display text-base font-semibold text-app-primary">Guided Preparation</h3>
        </div>
        <div className="grid sm:grid-cols-2 gap-3">
          {guidedPreparation.map((prep, i) => {
            const Icon = prepIcons[prep.icon] || Lightbulb;
            return (
              <Card key={i} className="hover:border-brand-400/20 transition cursor-pointer" >
                <div onClick={() => handlePrepAction(prep)} className="flex flex-col h-full">
                  <div className="flex items-start gap-3 mb-3">
                    <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-brand-500/15 text-brand-300 flex-shrink-0">
                      <Icon size={17} />
                    </div>
                    <div className="flex-1">
                      <h4 className="text-sm font-medium text-app-primary">{prep.title}</h4>
                    </div>
                  </div>
                  <p className="text-xs text-app-muted flex-1 leading-relaxed">{prep.desc}</p>
                  <div className="flex items-center gap-1 mt-3 text-xs text-brand-300 font-medium">
                    {prep.action}
                    <ArrowRight size={12} />
                  </div>
                </div>
              </Card>
            );
          })}
        </div>
      </div>

      {/* FAQ Section */}
      <Card>
        <div className="flex items-center gap-2 mb-4">
          <HelpCircle size={16} className="text-app-muted" />
          <h3 className="font-display text-base font-semibold text-app-primary">Frequently Asked Questions</h3>
        </div>
        <div className="space-y-2">
          {applicationFAQs.map((faq, i) => (
            <div key={i} className="rounded-lg border border-app-soft overflow-hidden">
              <button
                onClick={() => setOpenFaq(openFaq === i ? null : i)}
                className="flex items-center justify-between w-full p-3 text-left hover:bg-app-hover transition"
              >
                <span className="text-sm font-medium text-app-primary">{faq.q}</span>
                <ChevronDown size={15} className={cn("text-app-faint flex-shrink-0 transition-transform", openFaq === i && "rotate-180")} />
              </button>
              {openFaq === i && (
                <div className="px-3 pb-3">
                  <p className="text-sm text-app-muted leading-relaxed">{faq.a}</p>
                </div>
              )}
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
