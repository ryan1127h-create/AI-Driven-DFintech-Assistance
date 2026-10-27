/* eslint-disable react/prop-types */
import { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Users } from "lucide-react";
import {
  acceptAlumniRequest, cancelAlumniRequest, createAlumniRequest, declineAlumniRequest,
  getAlumniMatches, getAlumniMe, getAlumniRequests, setAlumniListed, setAlumniStorySharing,
} from "../../api";
import { LoadingState, PageHeader } from "../components/student/PageParts";
import { formatDate } from "../utils/format";

// Alumni Match has two sides. Enrolled students browse listed alumni and send
// requests; alumni answer them. Contact details appear only once a request is
// accepted, and only those the alumnus chose to share. Emails open in the
// user's own mail app (mailto) — nothing is sent by the system.

function Icon({ name, size = 20 }) {
  const paths = {
    sparkles: <><path d="m12 3-1.2 3.2L8 7.5l2.8 1.3L12 12l1.2-3.2L16 7.5l-2.8-1.3L12 3Z" /><path d="m5.5 12-.8 2.2-2.2.8 2.2.8.8 2.2.8-2.2 2.2-.8-2.2-.8-.8-2.2Z" /></>,
    link: <><path d="M15 7h2a5 5 0 0 1 0 10h-2M9 17H7A5 5 0 0 1 7 7h2M8 12h8" /></>,
    message: <path d="M21 15a4 4 0 0 1-4 4H8l-5 3V7a4 4 0 0 1 4-4h10a4 4 0 0 1 4 4Z" />,
    user: <><circle cx="12" cy="8" r="4" /><path d="M4 21a8 8 0 0 1 16 0" /></>,
    chevron: <path d="m9 18 6-6-6-6" />,
    search: <><circle cx="11" cy="11" r="7" /><path d="m20 20-4-4" /></>,
    plusUser: <><path d="M15 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" /><circle cx="8.5" cy="7" r="4" /><path d="M19 8v6M16 11h6" /></>,
    lock: <><rect x="4" y="10" width="16" height="11" rx="2" /><path d="M8 10V7a4 4 0 0 1 8 0v3" /></>,
    close: <><path d="m6 6 12 12M18 6 6 18" /></>,
    check: <path d="m5 12 4 4L19 6" />,
    mail: <><rect x="3" y="5" width="18" height="14" rx="2" /><path d="m3 7 9 6 9-6" /></>,
    building: <><path d="M4 21V3h12v18M16 9h4v12M8 7h4M8 11h4M8 15h4M2 21h20" /></>,
    briefcase: <><rect x="3" y="7" width="18" height="13" rx="2" /><path d="M8 7V5a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2M3 12h18" /></>,
    filter: <path d="M4 5h16M7 12h10M10 19h4" />,
  };
  return <svg aria-hidden="true" width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">{paths[name]}</svg>;
}

function Button({ children, variant = "primary", icon, onClick, disabled, className = "", type = "button" }) {
  return <button type={type} className={`btn btn-${variant} ${className}`} onClick={onClick} disabled={disabled}>{icon && <Icon name={icon} size={17} />}<span>{children}</span></button>;
}

function Avatar({ src, name, size = "md" }) {
  if (src) return <img className={`avatar avatar-${size}`} src={src} alt={`${name} profile`} />;
  const initials = (name || "?").split(/\s+/).slice(0, 2).map((part) => part[0]).join("").toUpperCase();
  return <span className={`avatar avatar-${size} avatar-initials`} aria-hidden="true">{initials}</span>;
}

function ExpertiseTags({ items, max = 3 }) {
  return <div className="tag-list">{items.slice(0, max).map((tag) => <span className="tag" key={tag.tag}>{tag.label}</span>)}{items.length > max && <span className="tag-more">+{items.length - max} more</span>}</div>;
}

function ModalShell({ children, onClose, wide = false }) {
  return <div className="overlay modal-overlay" onMouseDown={onClose}><div className={`modal ${wide ? "modal-wide" : ""}`} role="dialog" aria-modal="true" onMouseDown={(e) => e.stopPropagation()}>{children}</div></div>;
}

// The whole name: the first word isn't reliably the given name (Chen Yuxin).
const displayName = (name) => (name || "").trim();
// Must match the consent_alumni_matching description (0033) and the fields
// tagged with purpose "alumni": what an alumnus sees about a requesting student.
const SHARED_WITH_ALUMNI = "your name, study stage, graduation term, whether you are looking for a mentor, your target roles, degree discipline, work experience, preferred job markets, job search timeline and your note";
const mailto = (to, subject, body) => `mailto:${to}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;
const STATUS_LABELS = { pending: "Waiting for a reply", accepted: "Connected", declined: "Declined" };

// --- student side -----------------------------------------------------------------

function AlumniCard({ person, onView, onConnect, canSend }) {
  const status = person.request?.status;
  return <article className="alumni-card" onClick={onView}>
    <div className="card-accent" />
    <div className="card-top"><Avatar src={person.photo_url} name={person.name} /><span className="open-profile">View profile <Icon name="chevron" size={14} /></span></div>
    <div className="card-person">
      <h3>{person.name}</h3>
      <p><Icon name="briefcase" size={15} />{person.position}</p>
      <p><Icon name="building" size={15} />{person.company}{person.class_year ? ` · Class of ${person.class_year}` : ""}</p>
    </div>
    {person.matched.length > 0 && <p className="match-reason"><Icon name="sparkles" size={14} />Matches your interest in {person.matched.join(", ")}</p>}
    <div className="expertise-block"><span>EXPERTISE</span><ExpertiseTags items={person.expertise} /></div>
    <span onClick={(e) => e.stopPropagation()}>
      {status ? <Button icon="check" disabled className="card-connect">{STATUS_LABELS[status]}</Button>
        : <Button icon="plusUser" disabled={!canSend} onClick={onConnect} className="card-connect">Connect</Button>}
    </span>
  </article>;
}

function ProfileDrawer({ person, canSend, onClose, onConnect }) {
  const status = person.request?.status;
  return <div className="overlay drawer-overlay" onMouseDown={onClose}>
    <aside className="profile-drawer" aria-label={`${person.name} profile`} onMouseDown={(e) => e.stopPropagation()}>
      <div className="drawer-head"><span>Alumni profile</span><button type="button" className="icon-button" aria-label="Close" onClick={onClose}><Icon name="close" /></button></div>
      <div className="profile-hero">
        <div className="profile-cover" />
        <Avatar src={person.photo_url} name={person.name} size="lg" />
        <div className="profile-title"><h2>{person.name}</h2><p>{person.position}</p><span>{person.company}</span></div>
        <span className={`status-pill ${status === "accepted" ? "connected" : ""}`}><i />{status ? STATUS_LABELS[status] : "Not connected"}</span>
        {!status && <Button icon="plusUser" disabled={!canSend} onClick={onConnect}>Send a request</Button>}
      </div>
      <div className="drawer-content">
        <section><div className="section-heading"><Icon name="briefcase" size={19} /><h3>Professional information</h3></div><div className="info-grid"><div><span>Current company</span><strong>{person.company}</strong></div><div><span>Current position</span><strong>{person.position}</strong></div>{person.class_year && <div><span>Class of</span><strong>{person.class_year}</strong></div>}</div>{person.bio && <p className="drawer-bio">{person.bio}</p>}</section>
        <section><div className="section-heading"><Icon name="sparkles" size={19} /><h3>Expertise</h3></div><ExpertiseTags items={person.expertise} max={12} /></section>
        <section><div className="section-heading"><Icon name="user" size={19} /><h3>Contact information</h3></div>
          <div className="privacy-card"><div className="privacy-icon"><Icon name="lock" /></div><div><strong>Contact information is private</strong><p>If {displayName(person.name)} accepts your request, the contact details they choose to share appear under My Requests.</p></div></div>
        </section>
      </div>
    </aside>
  </div>;
}

function ConnectModal({ person, onClose, onSend, busy, error }) {
  const [note, setNote] = useState("");
  return <ModalShell onClose={onClose}>
    <div className="modal-header"><div className="modal-symbol"><Icon name="plusUser" /></div><button type="button" className="icon-button" aria-label="Close" onClick={onClose}><Icon name="close" /></button></div>
    <h2>Connect with {displayName(person.name)}?</h2><p className="modal-lead">{displayName(person.name)} will see {SHARED_WITH_ALUMNI}.</p>
    <div className="mini-profile"><Avatar src={person.photo_url} name={person.name} size="sm" /><div><strong>{person.name}</strong><span>{person.position} at {person.company}</span></div></div>
    <label className="field-label" htmlFor="note">Add a note <span>(optional)</span></label>
    <div className="textarea-wrap"><textarea id="note" value={note} maxLength={300} onChange={(e) => setNote(e.target.value)} placeholder={`Hi ${displayName(person.name)}, I'd like to hear about your path into ${person.expertise[0]?.label || "your field"}...`} /><span>{note.length}/300</span></div>
    {error && <p role="alert" className="form-error">{error}</p>}
    <div className="modal-actions"><Button variant="secondary" onClick={onClose}>Cancel</Button><Button icon="plusUser" disabled={busy} onClick={() => onSend(note.trim())}>{busy ? "Sending…" : "Send request"}</Button></div>
  </ModalShell>;
}

// Requests still waiting for an answer, and declined ones (so the student
// knows they may ask again). Accepted ones live under My Connections.
function SentRequests({ requests, onCancel, busyId, onFind }) {
  if (!requests.length) return <div className="request-empty"><Icon name="check" size={20} /><span>No open requests. </span><button type="button" className="link-button" onClick={onFind}>Find alumni to contact</button></div>;
  return <div className="request-list">{requests.map((r) => <article className={`request-card ${r.status === "declined" ? "is-declined" : ""}`} key={r.id}>
    <Avatar src={r.alumnus.photo_url} name={r.alumnus.name} />
    <div className="request-main">
      <div className="request-name"><h3>{r.alumnus.name}</h3><span className={r.status === "declined" ? "declined-pill" : "pending-pill"}>{STATUS_LABELS[r.status]}</span></div>
      <p>{r.alumnus.position} at {r.alumnus.company} · Sent {formatDate(r.created_at)}{r.status === "declined" && r.responded_at ? ` · Declined ${formatDate(r.responded_at)}` : ""}</p>
      {r.note ? <blockquote>“{r.note}”</blockquote> : <p className="no-note">No note added.</p>}
      {r.status === "declined" && <p className="ranking-note">You can send {displayName(r.alumnus.name)} a new request from Find Alumni.</p>}
    </div>
    {r.status === "pending" && <div className="request-actions"><Button variant="ghost" disabled={busyId === r.id} onClick={() => onCancel(r.id)}>Withdraw</Button></div>}
  </article>)}</div>;
}

// Accepted requests: the alumnus's reply and the contact details they chose to share.
function StudentConnections({ connections, onFind }) {
  if (!connections.length) return <div className="empty-connections"><div className="empty-icon"><Icon name="link" size={30} /></div><h2>Your alumni connections</h2><p>Alumni who accept your requests appear here, with the contact details they choose to share.</p><Button variant="secondary" onClick={onFind}>Find alumni</Button></div>;
  return <div className="request-list">{connections.map((r) => {
    const contact = r.contact || {};
    const shared = contact.email || contact.linkedin || contact.phone;
    return <article className="request-card connection-card" key={r.id}>
      <Avatar src={r.alumnus.photo_url} name={r.alumnus.name} />
      <div className="request-main">
        <div className="request-name"><h3>{r.alumnus.name}</h3><span className="connected-label"><Icon name="check" size={13} />Connected</span></div>
        <p>{r.alumnus.position} at {r.alumnus.company}{r.responded_at ? ` · Connected ${formatDate(r.responded_at)}` : ""}</p>
        {r.reply_note && <blockquote><strong>{displayName(r.alumnus.name)}:</strong> “{r.reply_note}”</blockquote>}
        {shared ? <dl className="summary-background contact-list">
          {contact.email && <div><dt>Email</dt><dd>{contact.email}</dd></div>}
          {contact.phone && <div><dt>Phone</dt><dd>{contact.phone}</dd></div>}
          {contact.linkedin && <div><dt>LinkedIn</dt><dd>{contact.linkedin.replace(/^https?:\/\/(www\.)?/, "")}</dd></div>}
        </dl> : <p className="no-note">{displayName(r.alumnus.name)} accepted without sharing contact details.</p>}
      </div>
      {(contact.email || contact.linkedin) && <div className="request-actions">
        {contact.email && <a className="btn btn-primary" href={mailto(contact.email, "Hello from an MSc DFinTech student", `Hi ${displayName(r.alumnus.name)},\n\nThank you for accepting my request on Alumni Match.\n\n`)}><Icon name="mail" size={17} /><span>Email</span></a>}
        {contact.linkedin && <a className="btn btn-secondary" href={contact.linkedin} target="_blank" rel="noreferrer"><Icon name="link" size={17} /><span>LinkedIn</span></a>}
      </div>}
    </article>;
  })}</div>;
}

function StudentView({ notify }) {
  const [tab, setTab] = useState("find");
  const [search, setSearch] = useState("");
  const [expertise, setExpertise] = useState([]);
  const [data, setData] = useState(null);
  const [sent, setSent] = useState([]);
  const [error, setError] = useState("");
  const [viewing, setViewing] = useState(null);
  const [connecting, setConnecting] = useState(null);
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState("");

  // ?alumnus=<id> (a link from the chat) opens that alumnus's profile once the
  // listing has loaded.
  const [searchParams, setSearchParams] = useSearchParams();
  const linkedAlumnus = searchParams.get("alumnus");
  useEffect(() => {
    if (!linkedAlumnus || !data) return;
    const person = data.items.find((p) => p.id === linkedAlumnus);
    if (person) setViewing(person);
    setSearchParams((params) => { const next = new URLSearchParams(params); next.delete("alumnus"); return next; }, { replace: true });
  }, [linkedAlumnus, data, setSearchParams]);

  const loadRequests = useCallback(() => getAlumniRequests().then((r) => setSent(r.sent || [])).catch((e) => setError(e.message)), []);
  useEffect(() => {
    let active = true;
    const timer = setTimeout(() => {
      getAlumniMatches({ search: search.trim(), expertise }).then((d) => { if (active) { setData(d); setError(""); } }).catch((e) => { if (active) setError(e.message); });
    }, 250);
    return () => { active = false; clearTimeout(timer); };
  }, [search, expertise, sent]);
  useEffect(() => { loadRequests(); }, [loadRequests]);

  const send = async (note) => {
    setBusy(true); setActionError("");
    try { await createAlumniRequest({ alumniId: connecting.id, note }); setConnecting(null); setViewing(null); notify(`Request sent to ${connecting.name}.`); await loadRequests(); }
    catch (e) { setActionError(e.message); } finally { setBusy(false); }
  };
  const cancel = async (id) => {
    setBusy(id); try { await cancelAlumniRequest(id); notify("Request withdrawn."); await loadRequests(); } catch (e) { notify(e.message); } finally { setBusy(false); }
  };
  const toggleTag = (tag) => setExpertise((tags) => (tags.includes(tag) ? tags.filter((t) => t !== tag) : [...tags, tag]));
  const openRequests = sent.filter((r) => r.status !== "accepted");
  const connections = sent.filter((r) => r.status === "accepted");
  const pending = openRequests.filter((r) => r.status === "pending").length;
  const tabButton = (id, label, count) => <button type="button" role="tab" aria-selected={tab === id} className={tab === id ? "active" : ""} onClick={() => setTab(id)}>{label}{count !== undefined && <span>{count}</span>}</button>;

  return <>
    <div className="tabs" role="tablist">
      {tabButton("find", "Find Alumni")}
      {tabButton("sent", "My Requests", pending)}
      {tabButton("connections", "My Connections", connections.length)}
    </div>
    {error && <p role="alert" className="form-error">{error}</p>}
    {tab === "find" && <>
      {data && !data.can_send_requests && <div className="privacy-card"><div className="privacy-icon"><Icon name="lock" /></div><div><strong>Turn on alumni matching to send requests</strong><p>When you contact an alumnus, they see {SHARED_WITH_ALUMNI}. Turn on “Alumni matching” under Settings → Privacy first.</p></div></div>}
      <div className="filter-panel">
        <label className="search-wrap"><Icon name="search" size={17} /><input aria-label="Search alumni" placeholder="Search by name, position or company" value={search} onChange={(e) => setSearch(e.target.value)} /></label>
        <div className="chip-row"><Icon name="filter" size={15} />{(data?.expertise_options || []).map((o) => <button type="button" key={o.tag} className={`chip ${expertise.includes(o.tag) ? "active" : ""}`} aria-pressed={expertise.includes(o.tag)} onClick={() => toggleTag(o.tag)}>{expertise.includes(o.tag) && <Icon name="check" size={13} />}{o.label}</button>)}{(search || expertise.length > 0) && <button type="button" className="reset-filters" onClick={() => { setSearch(""); setExpertise([]); }}>Reset filters</button>}</div>
        {data && <div className="results-summary"><span><strong>{data.total}</strong> alumni found</span>{expertise.length > 0 && <span className="active-filter-summary">{expertise.length} active filter{expertise.length === 1 ? "" : "s"}</span>}</div>}
      </div>
      {!data ? <LoadingState className="alumni-loading" icon={Users} title="Loading alumni" subtitle="Finding matches for your interests…" /> : data.items.length ? <div className="alumni-grid">{data.items.map((person) => <AlumniCard key={person.id} person={person} canSend={data.can_send_requests} onView={() => setViewing(person)} onConnect={() => { setActionError(""); setConnecting(person); }} />)}</div>
        : <div className="alumni-no-results"><div className="alumni-no-results-icon"><Icon name="search" size={22} /></div><strong>No alumni match your search yet</strong><span>Try removing a filter or searching by a broader role, company, or skill.</span>{(search || expertise.length > 0) && <button type="button" onClick={() => { setSearch(""); setExpertise([]); }}>Clear filters</button>}</div>}
    </>}
    {tab === "sent" && <SentRequests requests={openRequests} onCancel={cancel} busyId={busy} onFind={() => setTab("find")} />}
    {tab === "connections" && <StudentConnections connections={connections} onFind={() => setTab("find")} />}
    {viewing && <ProfileDrawer person={viewing} canSend={data?.can_send_requests} onClose={() => setViewing(null)} onConnect={() => { setActionError(""); setConnecting(viewing); }} />}
    {connecting && <ConnectModal person={connecting} busy={busy} error={actionError} onClose={() => setConnecting(null)} onSend={send} />}
  </>;
}

// --- alumni side ------------------------------------------------------------------

// The requesting student as the alumnus sees them: why they match, their
// background and their note. Only what the student consented to share.
function StudentSummary({ student, note, createdAt }) {
  const { match = {}, background = [] } = student;
  const otherInterests = (match.other || []).filter((role) => role !== match.main_role);
  return <div className="student-summary">
    <div className="request-name"><h3>{student.name}</h3>{student.mentor_seeking && <span className="pending-pill">Looking for a mentor</span>}</div>
    <p>{student.stage}{createdAt ? ` · Sent ${formatDate(createdAt)}` : ""}</p>
    <div className="summary-row"><span>MATCH</span>
      {match.shared?.length ? <strong className="match-shared"><Icon name="sparkles" size={14} />Shared interests: {match.shared.join(", ")}{match.main_role_shared ? " (their main target role)" : ""}</strong>
        : <strong>No overlap with your expertise</strong>}
      {match.main_role && !match.main_role_shared && <small>Main target role: {match.main_role}</small>}
      {otherInterests.length > 0 && <small>Also interested in: {otherInterests.join(", ")}</small>}
    </div>
    {background.length > 0 && <dl className="summary-background">{background.map((item) => <div key={item.label}><dt>{item.label}</dt><dd>{item.value}</dd></div>)}</dl>}
    {note ? <blockquote>“{note}”</blockquote> : <p className="no-note">No note added.</p>}
  </div>;
}

const CONTACT_FIELDS = [["email", "contact_email", "Share my email", "mail"], ["phone", "contact_phone", "Share my phone number", "message"], ["linkedin", "linkedin_url", "Share my LinkedIn", "link"]];

function AcceptModal({ request, profile, onClose, onAccept, busy, error }) {
  const available = CONTACT_FIELDS.filter(([, column]) => profile?.[column]);
  const [share, setShare] = useState([]);
  const [note, setNote] = useState("");
  const toggle = (key) => setShare((keys) => (keys.includes(key) ? keys.filter((k) => k !== key) : [...keys, key]));
  return <ModalShell onClose={onClose} wide>
    <div className="modal-header"><div className="modal-symbol green"><Icon name="link" /></div><button type="button" className="icon-button" aria-label="Close" onClick={onClose}><Icon name="close" /></button></div>
    <h2>Accept request</h2><p className="modal-lead">You are about to connect with <strong>{request.student.name}</strong>. Choose exactly what to share.</p>
    <div className="accept-summary"><StudentSummary student={request.student} note={request.note} createdAt={request.created_at} /></div>
    <div className="permission-panel">
      <div className="permission-title"><div className="privacy-icon"><Icon name="lock" size={19} /></div><div><strong>Share my contact information</strong><span>Nothing is shared unless you select it</span></div></div>
      {available.length ? available.map(([key, column, label, icon]) => <label key={key} className={`check-option ${share.includes(key) ? "selected" : ""}`}><input type="checkbox" checked={share.includes(key)} onChange={() => toggle(key)} /><span className="fake-check">{share.includes(key) && <Icon name="check" size={14} />}</span><Icon name={icon} /><div><strong>{label}</strong><span>{profile[column]}</span></div></label>)
        : <p className="permission-help">Your directory entry has no contact details yet. Ask the programme office to add them.</p>}
      <label className="field-label permission-note-label" htmlFor="alumni-note">Add a note <span>(optional)</span></label>
      <div className="textarea-wrap"><textarea id="alumni-note" value={note} maxLength={300} onChange={(e) => setNote(e.target.value)} placeholder={`Welcome, ${displayName(request.student.name)}. Happy to share career advice...`} /><span>{note.length}/300</span></div>
      <p className="permission-help"><Icon name="lock" size={14} />Only what you select and your note are shared. You can accept without sharing contact details.</p>
    </div>
    {error && <p role="alert" className="form-error">{error}</p>}
    <div className="modal-actions"><Button variant="secondary" onClick={onClose}>Cancel</Button><Button icon="check" disabled={busy} onClick={() => onAccept(share, note.trim())}>{busy ? "Accepting…" : "Accept"}</Button></div>
  </ModalShell>;
}

function emailToStudent(request, profile) {
  const shared = request.shared_contact || {};
  const lines = [shared.email && `Email: ${shared.email}`, shared.phone && `Phone: ${shared.phone}`, shared.linkedin && `LinkedIn: ${shared.linkedin}`].filter(Boolean);
  const body = `Hi ${displayName(request.student.name)},\n\nThanks for reaching out on Alumni Match — happy to connect.\n\n${lines.length ? `${lines.join("\n")}\n\n` : ""}${request.reply_note ? `${request.reply_note}\n\n` : ""}Best regards`;
  return mailto(request.student.email, `Alumni Match: connecting with ${profile?.company ? `an alumnus at ${profile.company}` : "an MSc DFinTech alumnus"}`, body);
}

// Whether the assistant may show this alumnus's story (position, company,
// class year and bio — never contact details) to each audience. Separate
// from being listed, which is about being found and contacted.
const STORY_AUDIENCES = [
  { flag: "story_for_applicants", label: "Prospective students and applicants", audience: "prospective students" },
  { flag: "story_for_students", label: "Current students", audience: "current students" },
];

function StorySharing({ profile, onToggle }) {
  return <div className="privacy-card story-card">
    <div className="privacy-icon"><Icon name="sparkles" /></div>
    <div>
      <strong>Share your story</strong>
      <p>The assistant can mention your path — position, company, class year and bio — to readers with similar goals. Your contact details are never shown.</p>
      <div className="story-toggles">
        {STORY_AUDIENCES.map(({ flag, label, audience }) => (
          <label key={flag} className="story-toggle">
            <input type="checkbox" checked={Boolean(profile[flag])} onChange={() => onToggle(flag, audience)} />
            <span>{label}</span>
          </label>
        ))}
      </div>
    </div>
  </div>;
}

function AlumniView({ notify }) {
  const [tab, setTab] = useState("requests");
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [accepting, setAccepting] = useState(null);
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState("");
  const load = useCallback(() => getAlumniRequests().then((d) => { setData(d); setError(""); }).catch((e) => setError(e.message)), []);
  useEffect(() => { load(); }, [load]);

  const accept = async (share, replyNote) => {
    setBusy(true); setActionError("");
    try { await acceptAlumniRequest(accepting.id, { share, replyNote }); notify(`You are now connected with ${accepting.student.name}.`); setAccepting(null); setTab("connections"); await load(); }
    catch (e) { setActionError(e.message); } finally { setBusy(false); }
  };
  const decline = async (request) => {
    if (!window.confirm(`Decline ${request.student.name}'s request?`)) return;
    try { await declineAlumniRequest(request.id); notify("Request declined."); await load(); } catch (e) { notify(e.message); }
  };
  const toggleListed = async () => {
    try { await setAlumniListed(!data.profile.listed); notify(data.profile.listed ? "You are now hidden from students." : "Students can now find you."); await load(); } catch (e) { notify(e.message); }
  };
  const toggleStory = async (flag, audience) => {
    const on = !data.profile[flag];
    try { await setAlumniStorySharing({ [flag]: on }); notify(on ? `Your story can now be shown to ${audience}.` : `Your story is no longer shown to ${audience}.`); await load(); } catch (e) { notify(e.message); }
  };

  if (error) return <p role="alert" className="form-error">{error}</p>;
  if (!data) return <LoadingState className="alumni-loading" icon={Users} title="Loading requests" subtitle="Checking your connection requests…" />;
  const pending = data.incoming.filter((r) => r.status === "pending");
  const connected = data.incoming.filter((r) => r.status === "accepted");
  return <>
    {data.profile ? <div className="privacy-card listing-card"><div className="privacy-icon"><Icon name={data.profile.listed ? "check" : "lock"} /></div><div><strong>{data.profile.listed ? "You are listed in the alumni directory" : "You are hidden from students"}</strong><p>{data.profile.listed ? "Enrolled students can find you and send requests." : "Students can't see you until you choose to be listed."}</p></div><Button variant={data.profile.listed ? "secondary" : "primary"} onClick={toggleListed}>{data.profile.listed ? "Hide me" : "List me"}</Button></div>
      : <div className="privacy-card"><div className="privacy-icon"><Icon name="lock" /></div><div><strong>Your directory entry hasn&apos;t been set up yet</strong><p>The programme office creates alumni entries. Once yours exists you can choose to be listed.</p></div></div>}
    {data.profile && <StorySharing profile={data.profile} onToggle={toggleStory} />}
    <div className="tabs" role="tablist">
      <button type="button" role="tab" aria-selected={tab === "requests"} className={tab === "requests" ? "active" : ""} onClick={() => setTab("requests")}>Requests <span>{pending.length}</span></button>
      <button type="button" role="tab" aria-selected={tab === "connections"} className={tab === "connections" ? "active" : ""} onClick={() => setTab("connections")}>My Connections</button>
    </div>
    {tab === "requests" && <div className="request-list">{pending.length ? pending.map((r) => <article className="request-card" key={r.id}>
      <Avatar name={r.student.name} /><div className="request-main"><StudentSummary student={r.student} note={r.note} createdAt={r.created_at} /></div>
      <div className="request-actions"><Button variant="danger" onClick={() => decline(r)}>Decline</Button><Button onClick={() => { setActionError(""); setAccepting(r); }}>Accept</Button></div>
    </article>) : <div className="request-empty"><Icon name="check" size={20} /><span>No requests waiting for you.</span></div>}</div>}
    {tab === "connections" && (connected.length ? <div className="connection-row">{connected.map((r) => <div className="student-connection" key={r.id}><Avatar name={r.student.name} size="sm" /><span><strong>{r.student.name}</strong><small>{r.student.stage}</small></span><a className="btn btn-primary" href={emailToStudent(r, data.profile)}><Icon name="mail" size={17} /><span>Email {displayName(r.student.name)}</span></a></div>)}</div>
      : <div className="empty-connections"><div className="empty-icon"><Icon name="link" size={30} /></div><h2>Your student connections</h2><p>Students whose requests you accept appear here, with a button that opens your email app to reply.</p></div>)}
    {accepting && <AcceptModal request={accepting} profile={data.profile} busy={busy} error={actionError} onClose={() => setAccepting(null)} onAccept={accept} />}
  </>;
}

export default function AlumniMatchPage() {
  const [role, setRole] = useState(null);
  const [error, setError] = useState("");
  const [toast, setToast] = useState("");
  useEffect(() => { getAlumniMe().then((me) => setRole(me.role)).catch((e) => setError(e.message)); }, []);
  const notify = useCallback((message) => { setToast(message); window.setTimeout(() => setToast(""), 3200); }, []);

  return <div className="alumni-match-page">
    <div className="main-shell"><main className="main">
      <PageHeader className="alumni-page-header" icon={Users} title="Alumni Match" subtitle={role === "alumni" ? "Help current students by answering their connection requests." : "Find MSc DFinTech alumni whose careers match your goals and ask to connect."} />
      {error && <p role="alert" className="form-error">{error}</p>}
      {role === "student" && <StudentView notify={notify} />}
      {role === "alumni" && <AlumniView notify={notify} />}
    </main></div>
    {toast && <div className="toast" role="status"><span><Icon name="check" size={16} /></span>{toast}<button type="button" aria-label="Dismiss" onClick={() => setToast("")}><Icon name="close" size={15} /></button></div>}
  </div>;
}
