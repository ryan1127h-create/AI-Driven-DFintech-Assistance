import {
  AlertTriangle, Network, Bot,
  BookOpen, ScrollText,
} from "lucide-react";
import {
  activityLogs,
} from "../../../data/mock";
import { Card } from "../../ui";
import { PageHeader } from "../../student/PageParts";
import { cn } from "../../../utils/cn";

export function ActivityLogsPage() {
  const typeIcons = { routing: Network, escalation: AlertTriangle, ai: Bot, kb: BookOpen };
  const typeColors = { routing: "text-brand-300", escalation: "text-amber-300", ai: "text-royal-300", kb: "text-cyan2-400" };
  return (
    <div>
      <PageHeader icon={ScrollText} title="Activity Logs" subtitle="System and agent activity audit trail" />
      <Card>
        <div className="space-y-1">
          {activityLogs.map((log) => {
            const Icon = typeIcons[log.type] || ScrollText;
            return (
              <div key={log.id} className="flex items-start gap-3 p-3 rounded-lg hover:bg-app-hover transition">
                <div className={cn("flex h-8 w-8 items-center justify-center rounded-lg bg-app-hover flex-shrink-0", typeColors[log.type])}>
                  <Icon size={15} />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-app-primary"><span className="font-medium text-app-primary">{log.actor}</span> {log.action}</p>
                  <p className="text-xs text-app-faint mt-0.5">{log.time}</p>
                </div>
              </div>
            );
          })}
        </div>
      </Card>
    </div>
  );
}
