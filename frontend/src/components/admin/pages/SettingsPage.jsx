import { useState } from "react";
import {
  Settings, Save, CheckCircle,
} from "lucide-react";
import { Card } from "../../ui";
import { PageHeader } from "../../student/PageParts";
import { cn } from "../../../utils/cn";

// ============ FUNCTIONAL SETTINGS PAGE ============

export function SettingsPage() {
  const [settings, setSettings] = useState({
    confidenceThreshold: 60,
    escalationThreshold: 50,
    intentDetectionMode: "hybrid",
    emailNotifications: true,
    reminderFrequency: "daily",
    escalationAlerts: true,
    defaultRoleAccess: "prospective",
    sessionTimeout: 30,
    theme: "dark",
    autoVersioning: true,
    approvalWorkflow: true,
    retentionPeriod: 7,
  });
  const [saved, setSaved] = useState(false);

  const update = (key, value) => {
    setSettings((prev) => ({ ...prev, [key]: value }));
    setSaved(false);
  };

  const handleSave = () => {
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  return (
    <div>
      <PageHeader icon={Settings} title="Settings" subtitle="System configuration and preferences" />

      <div className="grid lg:grid-cols-2 gap-4">
        {/* AI Settings */}
        <Card>
          <h3 className="font-display text-base font-semibold text-app-primary mb-4">AI Settings</h3>
          <div className="space-y-4">
            <div>
              <label className="text-sm text-app-secondary">Confidence Threshold: {settings.confidenceThreshold}%</label>
              <input type="range" min="0" max="100" value={settings.confidenceThreshold} onChange={(e) => update("confidenceThreshold", parseInt(e.target.value))} className="w-full mt-2 accent-brand-500" />
              <p className="text-xs text-app-faint mt-1">Responses below this confidence are flagged for review.</p>
            </div>
            <div>
              <label className="text-sm text-app-secondary">Escalation Threshold: {settings.escalationThreshold}%</label>
              <input type="range" min="0" max="100" value={settings.escalationThreshold} onChange={(e) => update("escalationThreshold", parseInt(e.target.value))} className="w-full mt-2 accent-brand-500" />
              <p className="text-xs text-app-faint mt-1">Responses below this confidence are auto-escalated.</p>
            </div>
            <div>
              <label className="text-sm text-app-secondary">Intent Detection Mode</label>
              <select value={settings.intentDetectionMode} onChange={(e) => update("intentDetectionMode", e.target.value)} className="input mt-1 text-sm">
                <option value="keyword">Keyword-based</option>
                <option value="semantic">Semantic (AI)</option>
                <option value="hybrid">Hybrid (Recommended)</option>
              </select>
            </div>
          </div>
        </Card>

        {/* Notification Settings */}
        <Card>
          <h3 className="font-display text-base font-semibold text-app-primary mb-4">Notification Settings</h3>
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-app-primary">Email Notifications</p>
                <p className="text-xs text-app-faint">Receive alerts via email</p>
              </div>
              <button onClick={() => update("emailNotifications", !settings.emailNotifications)} className={cn("relative h-6 w-11 rounded-full transition", settings.emailNotifications ? "bg-brand-500" : "bg-app-hover")}>
                <span className={cn("absolute top-0.5 h-5 w-5 rounded-full bg-app-primary transition-transform", settings.emailNotifications ? "translate-x-5" : "translate-x-0.5")} />
              </button>
            </div>
            <div>
              <label className="text-sm text-app-secondary">Reminder Frequency</label>
              <select value={settings.reminderFrequency} onChange={(e) => update("reminderFrequency", e.target.value)} className="input mt-1 text-sm">
                <option value="realtime">Real-time</option>
                <option value="hourly">Hourly</option>
                <option value="daily">Daily digest</option>
                <option value="weekly">Weekly summary</option>
              </select>
            </div>
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-app-primary">Escalation Alerts</p>
                <p className="text-xs text-app-faint">Notify on new escalations</p>
              </div>
              <button onClick={() => update("escalationAlerts", !settings.escalationAlerts)} className={cn("relative h-6 w-11 rounded-full transition", settings.escalationAlerts ? "bg-brand-500" : "bg-app-hover")}>
                <span className={cn("absolute top-0.5 h-5 w-5 rounded-full bg-app-primary transition-transform", settings.escalationAlerts ? "translate-x-5" : "translate-x-0.5")} />
              </button>
            </div>
          </div>
        </Card>

        {/* System Settings */}
        <Card>
          <h3 className="font-display text-base font-semibold text-app-primary mb-4">System Settings</h3>
          <div className="space-y-4">
            <div>
              <label className="text-sm text-app-secondary">Default Role Access</label>
              <select value={settings.defaultRoleAccess} onChange={(e) => update("defaultRoleAccess", e.target.value)} className="input mt-1 text-sm">
                <option value="prospective">Prospective Student</option>
                <option value="applicant">Applicant</option>
                <option value="enrolled">Enrolled Student</option>
              </select>
            </div>
            <div>
              <label className="text-sm text-app-secondary">Session Timeout: {settings.sessionTimeout} min</label>
              <input type="range" min="5" max="120" value={settings.sessionTimeout} onChange={(e) => update("sessionTimeout", parseInt(e.target.value))} className="w-full mt-2 accent-brand-500" />
            </div>
            <div>
              <label className="text-sm text-app-secondary">Theme Selection</label>
              <select value={settings.theme} onChange={(e) => update("theme", e.target.value)} className="input mt-1 text-sm">
                <option value="dark">Dark</option>
                <option value="light">Light</option>
                <option value="system">System default</option>
              </select>
            </div>
          </div>
        </Card>

        {/* Knowledge Base Settings */}
        <Card>
          <h3 className="font-display text-base font-semibold text-app-primary mb-4">Knowledge Base Settings</h3>
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-app-primary">Auto Versioning</p>
                <p className="text-xs text-app-faint">Automatically create versions on edit</p>
              </div>
              <button onClick={() => update("autoVersioning", !settings.autoVersioning)} className={cn("relative h-6 w-11 rounded-full transition", settings.autoVersioning ? "bg-brand-500" : "bg-app-hover")}>
                <span className={cn("absolute top-0.5 h-5 w-5 rounded-full bg-app-primary transition-transform", settings.autoVersioning ? "translate-x-5" : "translate-x-0.5")} />
              </button>
            </div>
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-app-primary">Approval Workflow</p>
                <p className="text-xs text-app-faint">Require admin approval before publishing</p>
              </div>
              <button onClick={() => update("approvalWorkflow", !settings.approvalWorkflow)} className={cn("relative h-6 w-11 rounded-full transition", settings.approvalWorkflow ? "bg-brand-500" : "bg-app-hover")}>
                <span className={cn("absolute top-0.5 h-5 w-5 rounded-full bg-app-primary transition-transform", settings.approvalWorkflow ? "translate-x-5" : "translate-x-0.5")} />
              </button>
            </div>
            <div>
              <label className="text-sm text-app-secondary">Document Retention Period: {settings.retentionPeriod} years</label>
              <input type="range" min="1" max="15" value={settings.retentionPeriod} onChange={(e) => update("retentionPeriod", parseInt(e.target.value))} className="w-full mt-2 accent-brand-500" />
            </div>
          </div>
        </Card>
      </div>

      <div className="flex items-center gap-3 mt-6">
        <button onClick={handleSave} className="btn-primary">
          <Save size={14} /> Save Settings
        </button>
        {saved && <span className="text-sm text-emerald2-400 flex items-center gap-1"><CheckCircle size={14} /> Settings saved</span>}
      </div>
    </div>
  );
}
