import {
  MessageSquare, Search, Filter,
} from "lucide-react";
import { Card, Badge } from "../../ui";
import { PageHeader } from "../../student/PageParts";

export function InquiriesPage() {
  const inquiries = [
    { id: "INQ-001", user: "Wei Jie Tan", role: "Prospective", query: "Am I eligible with a business degree?", agent: "Admissions Advisor", status: "automated", confidence: 0.94, time: "2 min ago" },
    { id: "INQ-002", user: "Mei Ling Chen", role: "Applicant", query: "When is the Round 2 deadline?", agent: "Admissions Advisor", status: "automated", confidence: 0.97, time: "8 min ago" },
    { id: "INQ-003", user: "Sofia Rahman", role: "Enrolled", query: "Can I take CS6202 next semester?", agent: "Academic Planner", status: "automated", confidence: 0.89, time: "15 min ago" },
    { id: "INQ-004", user: "Arjun Kumar", role: "Admitted", query: "What are my housing options?", agent: "Supervisor", status: "escalated", confidence: 0.51, time: "22 min ago" },
    { id: "INQ-005", user: "Daniel Lim", role: "Graduating", query: "How do I request my transcript?", agent: "Programme Knowledge", status: "automated", confidence: 0.96, time: "35 min ago" },
    { id: "INQ-006", user: "Priya Nair", role: "Alumni", query: "Find mentors in blockchain", agent: "Alumni Network", status: "automated", confidence: 0.88, time: "1h ago" },
  ];
  return (
    <div>
      <PageHeader icon={MessageSquare} title="Inquiries" subtitle="All AI-handled and escalated inquiries" />
      <Card className="mb-4 flex items-center gap-2">
        <Search size={16} className="text-app-faint" />
        <input placeholder="Search inquiries..." className="flex-1 bg-transparent text-sm text-app-primary placeholder:text-app-faint focus:outline-none" />
        <button className="btn-outline text-xs"><Filter size={14} /> Filter</button>
      </Card>
      <Card className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-app-subtle">
              <th className="text-left py-3 px-3 text-app-muted font-medium">ID</th>
              <th className="text-left py-3 px-3 text-app-muted font-medium">User</th>
              <th className="text-left py-3 px-3 text-app-muted font-medium">Query</th>
              <th className="text-left py-3 px-3 text-app-muted font-medium">Agent</th>
              <th className="text-left py-3 px-3 text-app-muted font-medium">Confidence</th>
              <th className="text-left py-3 px-3 text-app-muted font-medium">Status</th>
              <th className="text-left py-3 px-3 text-app-muted font-medium">Time</th>
            </tr>
          </thead>
          <tbody>
            {inquiries.map((q) => (
              <tr key={q.id} className="border-b border-app-soft hover:bg-app-hover transition">
                <td className="py-3 px-3 font-mono text-xs text-brand-300">{q.id}</td>
                <td className="py-3 px-3 text-app-primary">{q.user}<p className="text-[10px] text-app-faint">{q.role}</p></td>
                <td className="py-3 px-3 text-app-primary max-w-xs truncate">{q.query}</td>
                <td className="py-3 px-3 text-app-secondary text-xs">{q.agent}</td>
                <td className="py-3 px-3"><Badge color={q.confidence > 0.85 ? "emerald2" : q.confidence > 0.6 ? "amber" : "red"}>{Math.round(q.confidence * 100)}%</Badge></td>
                <td className="py-3 px-3">{q.status === "automated" ? <Badge color="emerald2">Automated</Badge> : <Badge color="amber">Escalated</Badge>}</td>
                <td className="py-3 px-3 text-xs text-app-faint">{q.time}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    </div>
  );
}
