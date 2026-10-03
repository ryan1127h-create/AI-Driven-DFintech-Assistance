import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Check, Lock, Moon, RotateCcw, ShieldCheck, Sparkles, Sun, Trash2, UserRound, X } from "lucide-react";
import { deleteCvData, getConsents, getSettings, updateConsents, updateMe, updateSettings } from "../../../api";
import { useRole } from "../../context/RoleContext";
import { useTheme } from "../../context/ThemeContext";
import { STAGE_LABELS } from "../../data/stages";
import { cn } from "../../utils/cn";
import { OptionChip, Switch } from "../ui";

// Account details, assistant preferences, and privacy and data controls,
// opened from the avatar menu at the bottom of the sidebar. The open
// section lives in the URL (?settings=privacy) so any page can link to it.

export const SETTINGS_SECTIONS = {
  account: { label: "Account", icon: UserRound },
  assistant: { label: "Assistant", icon: Sparkles },
  privacy: { label: "Privacy & data", icon: ShieldCheck },
};

const LANGUAGES = {
  en: "English", zh: "Chinese", ms: "Malay", ta: "Tamil", hi: "Hindi",
  id: "Indonesian", vi: "Vietnamese", th: "Thai", ja: "Japanese", ko: "Korean",
};
const ANSWER_DEPTHS = { concise: "Concise", standard: "Standard", detailed: "Detailed" };

function Row({ label, hint, children, inline }) {
  return (
    <div className={cn("py-4", inline ? "flex items-center justify-between gap-4" : "grid gap-2 sm:grid-cols-[minmax(0,170px)_minmax(0,1fr)] sm:gap-4")}>
      <div>
        <p className="text-sm text-app-secondary">{label}</p>
        {hint && <p className="mt-0.5 text-xs text-app-faint">{hint}</p>}
      </div>
      <div className={inline ? "flex-shrink-0" : "min-w-0"}>{children}</div>
    </div>
  );
}

function SectionTitle({ title, subtitle }) {
  return (
    <div className="mb-2">
      <h3 className="font-display text-base font-semibold text-app-primary">{title}</h3>
      {subtitle && <p className="mt-0.5 text-xs text-app-muted">{subtitle}</p>}
    </div>
  );
}

function AccountSection({ onReopenSetup, flash, fail }) {
  const { user, role, lifecycleStage, setCurrentUser } = useRole();
  const [name, setName] = useState(user?.name || "");
  const [saving, setSaving] = useState(false);
  const changed = name.trim() && name.trim() !== user?.name;

  const saveName = async (e) => {
    e.preventDefault();
    if (!changed) return;
    setSaving(true);
    try {
      setCurrentUser(await updateMe(name.trim()));
      flash("Name updated.");
    } catch (err) {
      fail(err.message || "Unable to update your name.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <>
      <div className="mb-4 flex items-center gap-4">
        <div className="flex h-14 w-14 flex-shrink-0 items-center justify-center rounded-2xl border border-brand-400/20 bg-gradient-to-br from-brand-500/20 to-royal-600/20 font-display text-xl font-bold text-brand-300">
          {user?.avatar}
        </div>
        <div className="min-w-0">
          <p className="truncate font-display text-lg font-semibold text-app-primary">{user?.name}</p>
          <div className="mt-1 flex flex-wrap gap-1.5">
            <span className="chip bg-brand-500/10 text-brand-300">
              {role === "admin" ? "Administrator" : STAGE_LABELS[lifecycleStage] || "Student"}
            </span>
          </div>
        </div>
      </div>
      <div className="divide-y divide-app-subtle">
        <Row label="Name">
          <form onSubmit={saveName} className="flex gap-2">
            <input className="input py-2" value={name} maxLength={255} onChange={(e) => setName(e.target.value)} />
            <button type="submit" className="btn-primary whitespace-nowrap px-4" disabled={!changed || saving}>
              {saving ? "Saving..." : "Save"}
            </button>
          </form>
        </Row>
        <Row label="Login email" hint="Used to sign in">
          <span className="inline-flex items-center gap-1.5 text-sm text-app-primary">
            {user?.email} <Lock size={12} className="text-app-faint" />
          </span>
        </Row>
        <Row label="Profile setup" hint="The short questionnaire from your first visit">
          <button type="button" className="btn-outline" onClick={onReopenSetup}>
            <RotateCcw size={14} /> Run it again
          </button>
        </Row>
      </div>
    </>
  );
}

function AssistantSection({ settings, onChange, busy }) {
  const { theme, setTheme } = useTheme();
  const languages = settings?.language_pref || [];
  const toggleLanguage = (code) =>
    onChange({ language_pref: languages.includes(code) ? languages.filter((c) => c !== code) : [...languages, code] });

  return (
    <>
      <p className="mb-2 text-xs text-app-muted">How the assistant talks to you.</p>
      <div className="divide-y divide-app-subtle">
        <Row label="Reply language" hint="Replies follow the language you write in; this is used when that can't be told, first choice first">
          <div className="flex flex-wrap gap-1.5">
            {Object.entries(LANGUAGES).map(([code, name]) => (
              <OptionChip key={code} active={languages.includes(code)} disabled={busy || !settings} onClick={() => toggleLanguage(code)}>
                {name}
              </OptionChip>
            ))}
          </div>
        </Row>
        <Row label="Answer detail">
          <div className="flex flex-wrap gap-1.5">
            {Object.entries(ANSWER_DEPTHS).map(([value, name]) => (
              <OptionChip key={value} active={settings?.answer_depth === value} disabled={busy || !settings}
                onClick={() => onChange({ answer_depth: value })}>{name}</OptionChip>
            ))}
          </div>
        </Row>
        <Row label="Email notifications" hint="Deadline reminders and event invitations" inline>
          <Switch label="Email notifications" checked={Boolean(settings?.email_notifications)} disabled={busy || !settings}
            onChange={(value) => onChange({ email_notifications: value })} />
        </Row>
        <Row label="Appearance">
          <div className="flex gap-1.5">
            <OptionChip active={theme === "light"} onClick={() => setTheme("light")}>
              <span className="inline-flex items-center gap-1.5"><Sun size={12} /> Light</span>
            </OptionChip>
            <OptionChip active={theme === "dark"} onClick={() => setTheme("dark")}>
              <span className="inline-flex items-center gap-1.5"><Moon size={12} /> Dark</span>
            </OptionChip>
          </div>
        </Row>
      </div>
    </>
  );
}

function PrivacySection({ consents, onConsent, onDeleteCv, busy }) {
  const [confirming, setConfirming] = useState(false);
  const [deleted, setDeleted] = useState(false);

  return (
    <>
      <SectionTitle title="Privacy" subtitle="Choose how your profile may be used. You can change these anytime." />
      <div className="divide-y divide-app-subtle">
        {consents.map((c) => (
          <Row key={c.key} label={c.label || c.key} hint={c.description} inline>
            <Switch label={c.label || c.key} checked={c.granted} disabled={busy} onChange={(value) => onConsent(c.key, value)} />
          </Row>
        ))}
      </div>

      <div className="mt-6">
        <SectionTitle
          title="Your CV data"
          subtitle="CV files are never stored. We keep the details found in them and the lines they came from, so you can see where a value came from."
        />
        {deleted ? (
          <p className="mt-3 inline-flex items-center gap-1.5 text-xs text-emerald2-400">
            <Check size={13} /> Deleted. The values on your profile stay.
          </p>
        ) : confirming ? (
          <div className="mt-3 flex flex-wrap items-center gap-2 rounded-lg border border-red-400/30 bg-red-500/5 px-3 py-2.5">
            <span className="flex-1 text-xs text-app-secondary">Delete everything kept from your CVs? Profile values stay.</span>
            <button type="button" className="btn-ghost px-3 py-1 text-xs" onClick={() => setConfirming(false)}>Cancel</button>
            <button type="button" className="btn-outline border-red-400/40 px-3 py-1 text-xs text-red-300" disabled={busy}
              onClick={async () => { if (await onDeleteCv()) setDeleted(true); setConfirming(false); }}>
              Delete
            </button>
          </div>
        ) : (
          <button type="button" className="btn-outline mt-3 text-red-300" onClick={() => setConfirming(true)}>
            <Trash2 size={14} /> Delete my CV data
          </button>
        )}
      </div>
    </>
  );
}

export default function SettingsDialog({ section, onSection, onClose }) {
  const navigate = useNavigate();
  const [settings, setSettings] = useState(null);
  const [consents, setConsents] = useState([]);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([getSettings(), getConsents()])
      .then(([sett, cons]) => {
        setSettings(sett);
        setConsents(cons);
      })
      .catch((err) => setError(err.message || "Unable to load your settings."));
  }, []);

  useEffect(() => {
    const onKey = (e) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const flash = (message) => {
    setError("");
    setNotice(message);
    setTimeout(() => setNotice(""), 2500);
  };

  const run = async (fn, message) => {
    setBusy(true);
    setError("");
    try {
      await fn();
      if (message) flash(message);
      return true;
    } catch (err) {
      setError(err.message || "Request failed.");
      return false;
    } finally {
      setBusy(false);
    }
  };

  const reopenSetup = () => {
    onClose();
    navigate("/app", { state: { openOnboarding: true } });
  };

  const current = SETTINGS_SECTIONS[section] ? section : "account";

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4 animate-fadeIn" onMouseDown={onClose}>
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Settings"
        onMouseDown={(e) => e.stopPropagation()}
        className="card flex h-[min(640px,90vh)] w-full max-w-3xl flex-col overflow-hidden p-0 sm:flex-row"
      >
        <nav className="flex flex-shrink-0 gap-1 border-b border-app-subtle p-3 sm:w-52 sm:flex-col sm:border-b-0 sm:border-r">
          <p className="hidden px-3 pb-2 pt-1 font-display text-base font-semibold text-app-primary sm:block">Settings</p>
          {Object.entries(SETTINGS_SECTIONS).map(([key, { label, icon: Icon }]) => (
            <button
              key={key}
              type="button"
              onClick={() => onSection(key)}
              className={cn("sidebar-item whitespace-nowrap text-left", key === current && "sidebar-item-active")}
            >
              <Icon size={15} /> {label}
            </button>
          ))}
        </nav>

        <div className="flex min-w-0 flex-1 flex-col">
          <div className="flex items-center justify-between gap-3 border-b border-app-subtle px-6 py-3">
            <p className="text-sm font-medium text-app-primary">{SETTINGS_SECTIONS[current].label}</p>
            <div className="flex items-center gap-3">
              {notice && <span className="inline-flex items-center gap-1 text-xs text-emerald2-400"><Check size={12} /> {notice}</span>}
              <button type="button" onClick={onClose} aria-label="Close settings"
                className="rounded-lg p-1.5 text-app-faint transition hover:bg-app-hover hover:text-app-primary">
                <X size={16} />
              </button>
            </div>
          </div>
          <div className="flex-1 overflow-y-auto px-6 py-5">
            {error && <p className="mb-4 rounded-lg border border-red-400/30 bg-red-500/10 px-3 py-2 text-sm text-red-300">{error}</p>}
            {current === "account" && (
              <AccountSection onReopenSetup={reopenSetup} flash={flash} fail={setError} />
            )}
            {current === "assistant" && (
              <AssistantSection settings={settings} busy={busy}
                onChange={(changes) => run(async () => setSettings(await updateSettings(changes)), "Saved")} />
            )}
            {current === "privacy" && (
              <PrivacySection
                consents={consents}
                busy={busy}
                onConsent={(key, granted) => run(async () => setConsents(await updateConsents({ [key]: granted })), "Saved")}
                onDeleteCv={() => run(() => deleteCvData(), "CV data deleted")}
              />
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
