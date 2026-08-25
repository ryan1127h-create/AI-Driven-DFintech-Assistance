import { useState } from "react";
import {
  AlertTriangle, Clock, Users,
  ArrowLeft, UserCheck, Bot,
  ChevronRight, Save, X, AlertCircle, Mail, Shield,
} from "lucide-react";
import {
  escalations as initialEscalations,
  escalationStatuses, staffMembers, staffTeams,
} from "../../../data/mock";
import { Card, Badge } from "../../ui";
import { PageHeader, StatusBadge } from "../../student/PageParts";
import { cn } from "../../../utils/cn";

// ============ ESCALATIONS WITH FULL CONVERSATION HISTORY ============

export function EscalationsPage() {
  const [cases, setCases] = useState(initialEscalations);
  const [selectedCase, setSelectedCase] = useState(null);
  const [showAssign, setShowAssign] = useState(false);
  const [assignForm, setAssignForm] = useState({ team: "", staff: "", priority: "medium", status: "open" });
  const [note, setNote] = useState("");

  const priorityColors = { urgent: "red", high: "amber", medium: "brand", low: "ink" };

  if (selectedCase) {
    const esc = cases.find((c) => c.id === selectedCase) || selectedCase;

    const handleAssign = () => {
      setCases((prev) => prev.map((c) =>
        c.id === esc.id ? { ...c, assigned: assignForm.staff || assignForm.team, assignedTeam: assignForm.team, priority: assignForm.priority, status: assignForm.staff || assignForm.team ? "assigned" : c.status } : c,
      ));
      setSelectedCase({ ...esc, assigned: assignForm.staff || assignForm.team, assignedTeam: assignForm.team, priority: assignForm.priority, status: assignForm.staff || assignForm.team ? "assigned" : esc.status });
      setShowAssign(false);
    };

    const addNote = () => {
      if (!note.trim()) return;
      setCases((prev) => prev.map((c) =>
        c.id === esc.id ? { ...c, notes: [...(c.notes || []), { author: "Dr. Lin Wei", text: note, time: "just now" }] } : c,
      ));
      setSelectedCase({ ...esc, notes: [...(esc.notes || []), { author: "Dr. Lin Wei", text: note, time: "just now" }] });
      setNote("");
    };

    return (
      <div>
        <button onClick={() => setSelectedCase(null)} className="btn-ghost mb-4 text-xs">
          <ArrowLeft size={14} /> Back to Escalations
        </button>

        {/* Case Summary */}
        <Card className="mb-4">
          <div className="flex items-start justify-between mb-4">
            <div>
              <p className="font-mono text-xs text-brand-300">{esc.id}</p>
              <h2 className="font-display text-lg font-bold text-app-primary mt-1">{esc.category}</h2>
              <p className="text-sm text-app-secondary mt-1">{esc.reason}</p>
            </div>
            <div className="flex items-center gap-2">
              <Badge color={priorityColors[esc.priority]}>{esc.priority}</Badge>
              <StatusBadge status={esc.status} />
            </div>
          </div>

          {/* User info */}
          <div className="grid sm:grid-cols-3 gap-3 pt-3 border-t border-app-subtle">
            <div className="flex items-center gap-2">
              <Users size={14} className="text-app-faint" />
              <div>
                <p className="text-xs text-app-faint">User</p>
                <p className="text-sm text-app-primary">{esc.user}</p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <Mail size={14} className="text-app-faint" />
              <div>
                <p className="text-xs text-app-faint">Email</p>
                <p className="text-sm text-app-primary">{esc.email}</p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <Shield size={14} className="text-app-faint" />
              <div>
                <p className="text-xs text-app-faint">Role</p>
                <p className="text-sm text-app-primary">{esc.role}</p>
              </div>
            </div>
          </div>

          {/* Escalation trigger */}
          <div className="mt-3 pt-3 border-t border-app-subtle flex items-center gap-2">
            <AlertCircle size={14} className="text-amber-300" />
            <span className="text-xs text-app-faint">Trigger:</span>
            <Badge color="amber">{esc.trigger}</Badge>
            <span className="text-xs text-app-faint ml-2">Confidence: <span className={esc.confidence > 0.6 ? "text-emerald2-400" : "text-amber-300"}>{Math.round(esc.confidence * 100)}%</span></span>
          </div>
        </Card>

        {/* Assignment */}
        <Card className="mb-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="font-display text-base font-semibold text-app-primary">Assignment</h3>
            {!showAssign ? (
              <button onClick={() => { setAssignForm({ team: esc.assignedTeam || "", staff: esc.assigned || "", priority: esc.priority, status: esc.status }); setShowAssign(true); }} className="btn-outline text-xs">
                {esc.assigned ? <><UserCheck size={12} /> Reassign</> : <><UserCheck size={12} /> Assign</>}
              </button>
            ) : (
              <button onClick={() => setShowAssign(false)} className="btn-ghost text-xs"><X size={12} /> Cancel</button>
            )}
          </div>

          {!showAssign ? (
            <div className="grid sm:grid-cols-4 gap-3">
              <div><p className="text-xs text-app-faint">Assigned Team</p><p className="text-sm text-app-primary">{esc.assignedTeam || "Unassigned"}</p></div>
              <div><p className="text-xs text-app-faint">Assigned Staff</p><p className="text-sm text-app-primary">{esc.assigned || "Unassigned"}</p></div>
              <div><p className="text-xs text-app-faint">Priority</p><p className="text-sm text-app-primary capitalize">{esc.priority}</p></div>
              <div><p className="text-xs text-app-faint">Status</p><StatusBadge status={esc.status} /></div>
            </div>
          ) : (
            <div className="grid sm:grid-cols-4 gap-3">
              <div>
                <label className="text-xs text-app-faint">Team</label>
                <select value={assignForm.team} onChange={(e) => setAssignForm({ ...assignForm, team: e.target.value })} className="input mt-1 text-sm">
                  <option value="">Select team</option>
                  {staffTeams.map((t) => <option key={t} value={t}>{t}</option>)}
                </select>
              </div>
              <div>
                <label className="text-xs text-app-faint">Staff</label>
                <select value={assignForm.staff} onChange={(e) => setAssignForm({ ...assignForm, staff: e.target.value })} className="input mt-1 text-sm">
                  <option value="">Select staff</option>
                  {staffMembers.map((s) => <option key={s} value={s}>{s}</option>)}
                </select>
              </div>
              <div>
                <label className="text-xs text-app-faint">Priority</label>
                <select value={assignForm.priority} onChange={(e) => setAssignForm({ ...assignForm, priority: e.target.value })} className="input mt-1 text-sm">
                  <option value="urgent">Urgent</option>
                  <option value="high">High</option>
                  <option value="medium">Medium</option>
                  <option value="low">Low</option>
                </select>
              </div>
              <div>
                <label className="text-xs text-app-faint">Status</label>
                <select value={assignForm.status} onChange={(e) => setAssignForm({ ...assignForm, status: e.target.value })} className="input mt-1 text-sm">
                  {escalationStatuses.map((s) => <option key={s} value={s}>{s}</option>)}
                </select>
              </div>
              <button onClick={handleAssign} className="btn-primary text-xs sm:col-span-4"><Save size={12} /> Save Assignment</button>
            </div>
          )}
        </Card>

        {/* Full Conversation History */}
        <Card className="mb-4">
          <h3 className="font-display text-base font-semibold text-app-primary mb-4">Conversation History</h3>
          <div className="space-y-3">
            {esc.conversation.map((msg, i) => (
              <div key={i} className={cn("flex gap-3", msg.role === "user" ? "justify-end" : "")}>
                {msg.role === "assistant" && (
                  <div className="flex h-8 w-8 items-center justify-center rounded-full bg-gradient-to-br from-brand-500 to-royal-600 text-app-primary flex-shrink-0">
                    <Bot size={14} />
                  </div>
                )}
                <div className={cn("max-w-md rounded-xl p-3", msg.role === "user" ? "bg-brand-500 text-app-primary" : "bg-app-hover")}>
                  <p className="text-sm">{msg.text}</p>
                  <div className="flex items-center gap-2 mt-2">
                    {msg.intent && <span className="text-[10px] text-app-faint">Intent: {msg.intent}</span>}
                    {msg.confidence != null && (
                      <span className={cn("text-[10px] font-medium", msg.confidence > 0.6 ? "text-emerald2-400" : "text-amber-300")}>
                        {Math.round(msg.confidence * 100)}% confidence
                      </span>
                    )}
                    <span className="text-[10px] text-app-faint ml-auto">{msg.time}</span>
                  </div>
                </div>
                {msg.role === "user" && (
                  <div className="flex h-8 w-8 items-center justify-center rounded-full bg-app-hover text-app-secondary flex-shrink-0">
                    <Users size={14} />
                  </div>
                )}
              </div>
            ))}
          </div>
        </Card>

        {/* Notes */}
        <Card>
          <h3 className="font-display text-base font-semibold text-app-primary mb-3">Case Notes</h3>
          <div className="space-y-2 mb-3">
            {(esc.notes || []).map((n, i) => (
              <div key={i} className="rounded-lg p-3 bg-app-hover border border-app-soft">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs font-medium text-app-primary">{n.author}</span>
                  <span className="text-[10px] text-app-faint">{n.time}</span>
                </div>
                <p className="text-sm text-app-secondary">{n.text}</p>
              </div>
            ))}
            {(!esc.notes || esc.notes.length === 0) && <p className="text-sm text-app-faint">No notes yet.</p>}
          </div>
          <div className="flex gap-2">
            <input value={note} onChange={(e) => setNote(e.target.value)} onKeyDown={(e) => e.key === "Enter" && addNote()} placeholder="Add a note..." className="input flex-1 text-sm" />
            <button onClick={addNote} className="btn-primary text-xs"><Save size={12} /> Add</button>
          </div>
        </Card>
      </div>
    );
  }

  return (
    <div>
      <PageHeader icon={AlertTriangle} title="Escalations" subtitle="Cases requiring human intervention" />
      <div className="grid lg:grid-cols-2 gap-4">
        {cases.map((e) => (
          <Card key={e.id} className="cursor-pointer hover:border-brand-400/20 transition" >
            <div onClick={() => setSelectedCase(e)}>
              <div className="flex items-start justify-between mb-3">
                <div>
                  <p className="font-mono text-xs text-brand-300">{e.id}</p>
                  <p className="font-medium text-app-primary text-sm mt-1">{e.user}</p>
                  <p className="text-xs text-app-muted">{e.role} · {e.category}</p>
                </div>
                <div className="flex items-center gap-2">
                  <Badge color={priorityColors[e.priority]}>{e.priority}</Badge>
                  <StatusBadge status={e.status} />
                </div>
              </div>
              <p className="text-sm text-app-secondary mb-3">{e.reason}</p>
              <div className="flex items-center justify-between text-xs">
                <span className="text-app-faint">Confidence: <span className={cn("font-medium", e.confidence > 0.6 ? "text-emerald2-400" : "text-amber-300")}>{Math.round(e.confidence * 100)}%</span></span>
                <span className="text-app-faint">Assigned: <span className="text-app-primary">{e.assigned || "Unassigned"}</span></span>
              </div>
              <div className="flex items-center gap-1 mt-3 text-xs text-brand-300 font-medium">
                View full conversation <ChevronRight size={12} />
              </div>
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}
