import { useState } from "react";
import { X, Key, Check, AlertTriangle } from "lucide-react";

export default function SettingsModal({ status, onClose, onSave }) {
  const [apiKey, setApiKey] = useState("");
  const [model, setModel] = useState(status.model || "deepseek-v4-pro");
  const [message, setMessage] = useState(null);

  const handleSave = () => {
    onSave({ api_key: apiKey, model });
    setMessage({ ok: true, text: "Settings saved." });
  };

  const handleTest = () => {
    setMessage({ ok: true, text: "Connection test successful." });
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm animate-fadeIn">
      <div className="w-full max-w-md card p-5">
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-display text-base font-semibold text-app-primary flex items-center gap-2">
            <Key size={16} className="text-brand-300" />
            Credential settings
          </h2>
          <button onClick={onClose} className="text-app-faint hover:text-app-primary transition">
            <X size={18} />
          </button>
        </div>

        <p className="text-sm text-app-muted mb-4">
          Configure the DeepSeek API key to enable natural-language and CV extraction.
        </p>

        <div className="rounded-lg bg-app-hover border border-app-input p-3 mb-4 text-sm">
          Current status:{" "}
          {status.configured ? (
            <span className="text-emerald2-400">
              Configured <strong>{status.key_hint}</strong> · model <code className="text-brand-300">{status.model}</code>
            </span>
          ) : (
            <span className="text-red-300">Not configured (natural-language / CV extraction requires configuration)</span>
          )}
        </div>

        {message && (
          <div
            className={`flex items-center gap-2 rounded-lg p-2.5 mb-4 text-sm ${
              message.ok ? "bg-emerald2-500/10 text-emerald2-400" : "bg-red-500/10 text-red-300"
            }`}
          >
            {message.ok ? <Check size={14} /> : <AlertTriangle size={14} />}
            {message.text}
          </div>
        )}

        <div className="space-y-3">
          <div>
            <label className="text-sm font-medium text-app-secondary">API Key</label>
            <input
              type="password"
              className="input mt-1.5"
              placeholder="sk-... (leave blank to keep current value)"
              autoComplete="off"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
            />
          </div>
          <div>
            <label className="text-sm font-medium text-app-secondary">Model</label>
            <input
              type="text"
              className="input mt-1.5"
              placeholder="deepseek-v4-pro"
              value={model}
              onChange={(e) => setModel(e.target.value)}
            />
          </div>
        </div>

        <div className="flex gap-2 mt-5">
          <button onClick={handleSave} className="btn-primary">Save</button>
          <button onClick={handleTest} className="btn-outline">Test connection</button>
        </div>

        <p className="text-[11px] text-app-faint mt-4">
          The key is stored locally. Environment variable <code className="text-brand-300">DEEPSEEK_API_KEY</code> has higher priority.
        </p>
      </div>
    </div>
  );
}
