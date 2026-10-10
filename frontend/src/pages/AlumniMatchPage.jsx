import { useEffect, useState } from "react";
import { Users } from "lucide-react";
import { getAlumniMatchData } from "../../api";
import { PageHeader } from "../components/student/PageParts";

function acceptAlumniRequest() {
  return Promise.resolve();
}

function Icon({ name, size = 20 }) {
  const paths = {
    grid: <><rect x="3" y="3" width="7" height="7" rx="1" /><rect x="14" y="3" width="7" height="7" rx="1" /><rect x="3" y="14" width="7" height="7" rx="1" /><rect x="14" y="14" width="7" height="7" rx="1" /></>,
    sparkles: <><path d="m12 3-1.2 3.2L8 7.5l2.8 1.3L12 12l1.2-3.2L16 7.5l-2.8-1.3L12 3Z" /><path d="m5.5 12-.8 2.2-2.2.8 2.2.8.8 2.2.8-2.2 2.2-.8-2.2-.8-.8-2.2Z" /><path d="m18.5 13-1 2.8-2.5 1.1 2.5 1 1 2.6 1-2.6 2.5-1-2.5-1.1-1-2.8Z" /></>,
    route: <><circle cx="6" cy="18" r="2" /><circle cx="18" cy="6" r="2" /><path d="M8 18h2a3 3 0 0 0 3-3V9a3 3 0 0 1 3-3" /></>,
    users: <><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" /><circle cx="9" cy="7" r="4" /><path d="M22 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75" /></>,
    link: <><path d="M15 7h2a5 5 0 0 1 0 10h-2M9 17H7A5 5 0 0 1 7 7h2M8 12h8" /></>,
    message: <path d="M21 15a4 4 0 0 1-4 4H8l-5 3V7a4 4 0 0 1 4-4h10a4 4 0 0 1 4 4Z" />,
    user: <><circle cx="12" cy="8" r="4" /><path d="M4 21a8 8 0 0 1 16 0" /></>,
    bell: <><path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9" /><path d="M10 21h4" /></>,
    chevron: <path d="m9 18 6-6-6-6" />,
    search: <><circle cx="11" cy="11" r="7" /><path d="m20 20-4-4" /></>,
    plusUser: <><path d="M15 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" /><circle cx="8.5" cy="7" r="4" /><path d="M19 8v6M16 11h6" /></>,
    lock: <><rect x="4" y="10" width="16" height="11" rx="2" /><path d="M8 10V7a4 4 0 0 1 8 0v3" /></>,
    close: <><path d="m6 6 12 12M18 6 6 18" /></>,
    check: <path d="m5 12 4 4L19 6" />,
    mail: <><rect x="3" y="5" width="18" height="14" rx="2" /><path d="m3 7 9 6 9-6" /></>,
    coffee: <><path d="M3 8h14v7a5 5 0 0 1-5 5H8a5 5 0 0 1-5-5V8Z" /><path d="M17 10h1a3 3 0 0 1 0 6h-1M7 2v3M11 2v3" /></>,
    building: <><path d="M4 21V3h12v18M16 9h4v12M8 7h4M8 11h4M8 15h4M2 21h20" /></>,
    briefcase: <><rect x="3" y="7" width="18" height="13" rx="2" /><path d="M8 7V5a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2M3 12h18" /></>,
    filter: <path d="M4 5h16M7 12h10M10 19h4" />,
    arrow: <><path d="M5 12h14M13 6l6 6-6 6" /></>,
  };
  return <svg aria-hidden="true" width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">{paths[name]}</svg>;
}

const photos = [];

function Button({ children, variant = "primary", icon, onClick, disabled, className = "" }) {
  return <button className={`btn btn-${variant} ${className}`} onClick={onClick} disabled={disabled}>{icon && <Icon name={icon} size={17} />}<span>{children}</span></button>;
}

function Avatar({ src, name, size = "md" }) {
  return <img className={`avatar avatar-${size}`} src={src} alt={`${name} profile`} />;
}

function ExpertiseTags({ items, max = 3 }) {
  return <div className="tag-list">{items.slice(0, max).map((tag) => <span className="tag" key={tag}>{tag}</span>)}{items.length > max && <span className="tag-more">+{items.length - max} more</span>}</div>;
}

function Sidebar() {
  const nav = [
    { label: "Alumni Match", icon: "users" },
  ];
  return <aside className="sidebar">
    <div className="brand"><div className="brand-mark"><span>A</span></div><div><strong>Alumni</strong><span>UNIVERSITY NETWORK</span></div></div>
    <nav className="nav">
      <p className="nav-label">WORKSPACE</p>
      {nav.map((item) => <button className={`nav-item ${item.label === "Alumni Match" ? "active" : ""}`} key={item.label}><Icon name={item.icon} size={19} /><span>{item.label}</span>{item.label === "Messages" && <i>2</i>}</button>)}
    </nav>
    <div className="sidebar-card"><div className="sidebar-card-icon"><Icon name="sparkles" size={18} /></div><strong>AI Career Assistant</strong><p>Get personalized guidance for your next career move.</p><button>Explore assistant <Icon name="arrow" size={14} /></button></div>
    <div className="sidebar-profile"><Avatar src={photos[1]} name="Emily Chen" size="sm" /><div><strong>Emily Chen</strong><span>Product leader · Class of 2018</span></div><Icon name="chevron" size={16} /></div>
  </aside>;
}

function Header({ requestCount, onRequests }) {
  return <header className="topbar">
    <div className="topbar-title"><span>ALUMNI NETWORK</span><strong>Find your people. Grow together.</strong></div>
    <div className="header-actions">
      <button className="icon-button request-bell" aria-label="Friend requests" onClick={onRequests}><Icon name="users" /><b>{requestCount}</b></button>
      <button className="icon-button" aria-label="Notifications"><Icon name="bell" /><i /></button>
      <div className="header-divider" />
      <Avatar src={photos[1]} name="Emily Chen" size="sm" />
      <div className="user-meta"><strong>Emily Chen</strong><span>Alumni mentor</span></div>
      <Icon name="chevron" size={16} />
    </div>
  </header>;
}

function AlumniCard({ person, requested, onView, onConnect }) {
  return <article className="alumni-card" onClick={onView}>
    <div className="card-accent" />
    <div className="card-top">
      <Avatar src={person.photo} name={person.name} />
      <span className="open-profile">View profile <Icon name="chevron" size={14} /></span>
    </div>
    <div className="card-person">
      <h3>{person.name}</h3>
      <p><Icon name="briefcase" size={15} />{person.position}</p>
      <p><Icon name="building" size={15} />{person.company}</p>
    </div>
    <div className="expertise-block"><span>EXPERTISE</span><ExpertiseTags items={person.expertise} /></div>
    <Button icon={requested ? "check" : "plusUser"} disabled={requested} onClick={() => { onConnect(); }} className="card-connect">{requested ? "Request Sent" : "Connect"}</Button>
  </article>;
}

function ProfileDrawer({ person, requested, connected, onClose, onConnect, onCoffee }) {
  return <div className="overlay drawer-overlay" onMouseDown={onClose}>
    <aside className="profile-drawer" onMouseDown={(e) => e.stopPropagation()}>
      <div className="drawer-head">
        <span>Alumni profile</span><button className="icon-button" onClick={onClose}><Icon name="close" /></button>
      </div>
      <div className="profile-hero">
        <div className="profile-cover" />
        <Avatar src={person.photo} name={person.name} size="lg" />
        <div className="profile-title"><h2>{person.name}</h2><p>{person.position}</p><span>{person.company}</span></div>
        <span className={`status-pill ${connected ? "connected" : ""}`}><i />{connected ? "Connected" : "Not Connected"}</span>
        {connected ? <Button icon="coffee" onClick={onCoffee}>Request a Coffee Chat</Button> : <Button icon={requested ? "check" : "plusUser"} disabled={requested} onClick={onConnect}>{requested ? "Request Sent" : "Send Friend Request"}</Button>}
      </div>
      <div className="drawer-content">
        <section><div className="section-heading"><Icon name="briefcase" size={19} /><h3>Professional information</h3></div><div className="info-grid"><div><span>Current company</span><strong>{person.company}</strong></div><div><span>Current position</span><strong>{person.position}</strong></div></div></section>
        <section><div className="section-heading"><Icon name="sparkles" size={19} /><h3>Expertise</h3></div><ExpertiseTags items={person.expertise} max={8} /></section>
        <section><div className="section-heading"><Icon name="user" size={19} /><h3>Contact information</h3></div>
          {connected ? <div className="privacy-card connected-card"><div className="privacy-icon"><Icon name="check" /></div><div><strong>You’re connected</strong><p>Contact details are shown only when this person has explicitly chosen to share them with you.</p></div></div>
          : <div className="privacy-card"><div className="privacy-icon"><Icon name="lock" /></div><div><strong>Contact information is private</strong><p>Connect with this alumni first. If your request is accepted, they can choose which contact details they would like to share with you.</p></div></div>}
        </section>
      </div>
    </aside>
  </div>;
}

function ModalShell({ children, onClose, wide = false }) {
  return <div className="overlay modal-overlay" onMouseDown={onClose}><div className={`modal ${wide ? "modal-wide" : ""}`} onMouseDown={(e) => e.stopPropagation()}>{children}</div></div>;
}

function ConnectModal({ person, onClose, onSend }) {
  const [note, setNote] = useState("");
  return <ModalShell onClose={onClose}>
    <div className="modal-header"><div className="modal-symbol"><Icon name="plusUser" /></div><button className="icon-button" onClick={onClose}><Icon name="close" /></button></div>
    <h2>Connect with {person.name.split(" ")[0]}?</h2><p className="modal-lead">Send a friend request to connect with this alumni.</p>
    <div className="mini-profile"><Avatar src={person.photo} name={person.name} size="sm" /><div><strong>{person.name}</strong><span>{person.position} at {person.company}</span></div></div>
    <label className="field-label" htmlFor="note">Add a note <span>(optional)</span></label>
    <div className="textarea-wrap"><textarea id="note" value={note} maxLength={300} onChange={(e) => setNote(e.target.value)} placeholder={`Hi ${person.name.split(" ")[0]}, I'm interested in learning more about your experience in machine learning...`} /><span>{note.length}/300</span></div>
    <div className="modal-actions"><Button variant="secondary" onClick={onClose}>Cancel</Button><Button icon="plusUser" onClick={onSend}>Send Friend Request</Button></div>
  </ModalShell>;
}

function AcceptModal({ onClose, onAccept }) {
  const [email, setEmail] = useState(false);
  const [phone, setPhone] = useState(false);
  const [linkedin, setLinkedin] = useState(false);
  const [note, setNote] = useState("");
  return <ModalShell onClose={onClose} wide>
    <div className="modal-header"><div className="modal-symbol green"><Icon name="link" /></div><button className="icon-button" onClick={onClose}><Icon name="close" /></button></div>
    <h2>Accept friend request</h2><p className="modal-lead">You are about to connect with <strong>Noor Aziz</strong>, a graduating student. Choose exactly what you would like to share with this connection.</p>
    <div className="permission-panel">
      <div className="permission-title"><div className="privacy-icon"><Icon name="lock" size={19} /></div><div><strong>Share my contact information</strong><span>Both options are private by default</span></div></div>
      <label className={`check-option ${email ? "selected" : ""}`}><input type="checkbox" checked={email} onChange={(e) => setEmail(e.target.checked)} /><span className="fake-check">{email && <Icon name="check" size={14} />}</span><Icon name="mail" /><div><strong>Share my email</strong><span>emily.chen@example.edu</span></div></label>
      <label className={`check-option ${phone ? "selected" : ""}`}><input type="checkbox" checked={phone} onChange={(e) => setPhone(e.target.checked)} /><span className="fake-check">{phone && <Icon name="check" size={14} />}</span><Icon name="message" /><div><strong>Share my phone number</strong><span>+65 8123 4567</span></div></label>
      <label className={`check-option ${linkedin ? "selected" : ""}`}><input type="checkbox" checked={linkedin} onChange={(e) => setLinkedin(e.target.checked)} /><span className="fake-check">{linkedin && <Icon name="check" size={14} />}</span><Icon name="link" /><div><strong>Share my LinkedIn</strong><span>linkedin.com/in/emilychen</span></div></label>
      <label className="field-label permission-note-label" htmlFor="alumni-note">Add a note <span>(optional)</span></label>
      <div className="textarea-wrap"><textarea id="alumni-note" value={note} maxLength={300} onChange={(e) => setNote(e.target.value)} placeholder="Welcome to my network, Noor. I’d be happy to share career advice..." /><span>{note.length}/300</span></div>
      <p className="permission-help"><Icon name="lock" size={14} />Only the information you select and the note you write will be shared. You can accept without sharing any contact details.</p>
    </div>
    <div className="share-preview"><span>SHARING PREVIEW</span><strong>{email || phone || linkedin ? [email && "Email", phone && "Phone", linkedin && "LinkedIn"].filter(Boolean).join(", ") : "No contact details"}</strong><p>{note.trim() ? "Your personal note will also be included." : "No personal note will be included."}</p></div>
    <div className="modal-actions"><Button variant="secondary" onClick={onClose}>Cancel</Button><Button icon="check" onClick={() => onAccept({ email, phone, linkedin, note: note.trim() })}>Accept Connection</Button></div>
  </ModalShell>;
}

function OutlookModal({ shared, onClose, onSend }) {
  const sharedLines = [
    shared.email && "Email: emily.chen@example.edu",
    shared.phone && "Phone: +65 8123 4567",
    shared.linkedin && "LinkedIn: https://linkedin.com/in/emilychen",
  ].filter(Boolean).join("\n");
  const body = `Hi Noor,\n\nEmily Chen has accepted your connection request.\n\n${sharedLines ? `Emily has chosen to share the following information with you:\n\n${sharedLines}\n\n` : "Emily has not shared any personal contact information at this time.\n\n"}${shared.note ? `A note from Emily:\n“${shared.note}”\n\n` : ""}You can now connect with Emily through the Alumni Match platform and request a Coffee Chat.\n\nBest regards,\nAlumni Match`;
  return <ModalShell onClose={onClose} wide>
    <div className="modal-header"><div className="modal-symbol outlook"><Icon name="mail" /></div><button className="icon-button" onClick={onClose}><Icon name="close" /></button></div>
    <h2>Send contact details</h2><p className="modal-lead">Review exactly what will be sent to Noor through Outlook. Selecting send will deliver this message immediately.</p>
    <div className="email-preview"><div><span>TO</span><strong>noor.aziz@student.edu</strong></div><div><span>SUBJECT</span><strong>Connection Accepted – Emily Chen</strong></div><pre>{body}</pre></div>
    <div className="consent-note"><Icon name="lock" size={16} />Only information shared with your explicit permission is included.</div>
    <div className="modal-actions"><Button variant="secondary" onClick={onClose}>Not now</Button><Button icon="mail" onClick={onSend}>Send through Outlook</Button></div>
  </ModalShell>;
}

function FriendRequests({ incomingRequest, onAccept, onDecline, connected, declined, shared, onOutlook }) {
  return <div className="requests-page">
    <div className="request-section-title"><div><h2>Incoming requests</h2><p>Graduating students who would like to connect with you</p></div><span>{connected || declined ? 0 : 1} pending</span></div>
    <div className="request-list">
      {!declined && <article className="request-card">
        <Avatar src={incomingRequest.photo} name={incomingRequest.name} /><div className="request-main"><div className="request-name"><h3>{incomingRequest.name}</h3>{connected && <span className="connected-label"><Icon name="check" size={13} />Connected</span>}</div><p>{incomingRequest.position}</p><ExpertiseTags items={incomingRequest.expertise} max={2} /><blockquote>“{incomingRequest.note}”</blockquote></div>
        <div className="request-actions"><Button variant="ghost">View Profile</Button>{!connected && <><Button variant="danger" onClick={onDecline}>Decline</Button><Button onClick={onAccept}>Accept Request</Button></>}{connected && shared && <Button icon="mail" onClick={onOutlook}>Send via Outlook</Button>}</div>
      </article>}
      {declined && <div className="request-empty"><Icon name="check" size={20} /><span>Request declined. There are no pending requests.</span></div>}
    </div>
  </div>;
}

function Connections({ connected, incomingRequest }) {
  return <div className="empty-connections"><div className="empty-icon"><Icon name="link" size={30} /></div><h2>Your student connections</h2><p>Graduating students whose requests you accept will appear here. You can then continue the conversation or prepare a Coffee Chat invitation.</p>{connected ? <div className="connection-row"><div className="student-connection"><Avatar src={incomingRequest.photo} name={incomingRequest.name} size="sm" /><span><strong>{incomingRequest.name}</strong><small>{incomingRequest.position}</small></span><i><Icon name="check" size={13} />Connected</i></div></div> : <span className="no-connections">No accepted student connections yet</span>}</div>;
}

export default function App() {
  const [matchData, setMatchData] = useState(null);
  const [tab, setTab] = useState("requests");
  const [modal, setModal] = useState(null);
  const [toast, setToast] = useState("");
  const [connected, setConnected] = useState(false);
  const [declined, setDeclined] = useState(false);
  const [shared, setShared] = useState(null);

  useEffect(() => {
    getAlumniMatchData().then(setMatchData).catch(() => setMatchData(null));
  }, []);

  if (!matchData) return <div className="alumni-match-page" />;
  const { alumni, incomingRequest } = matchData;
  const photos = alumni.map((person) => person.photo);

  const notify = (message) => { setToast(message); window.setTimeout(() => setToast(""), 3200); };
  const accept = (preferences) => {
    setConnected(true); setShared(preferences); acceptAlumniRequest(preferences); setModal(null); notify("Connection accepted. Your sharing preferences were saved.");
    window.setTimeout(() => setModal("outlook"), 450);
  };
  const decline = () => {
    setDeclined(true);
    notify("Friend request declined.");
  };
  const pendingCount = connected || declined ? 0 : 1;

  return <div className="alumni-match-page">
    <div className="main-shell">
      <main className="main">
        <PageHeader
          icon={Users}
          title="Alumni Match"
          subtitle="Support graduating students, manage connection requests, and arrange coffee chats."
        />
        <div className="tabs">
          <button className={tab === "requests" ? "active" : ""} onClick={() => setTab("requests")}>Friend Requests <span>{pendingCount}</span></button>
          <button className={tab === "connections" ? "active" : ""} onClick={() => setTab("connections")}>My Connections</button>
        </div>
        {tab === "requests" && <FriendRequests incomingRequest={incomingRequest} connected={connected} declined={declined} shared={shared} onAccept={() => setModal("accept")} onDecline={decline} onOutlook={() => setModal("outlook")} />}
        {tab === "connections" && <Connections incomingRequest={incomingRequest} connected={connected} />}
      </main>
    </div>
    {modal === "accept" && <AcceptModal onClose={() => setModal(null)} onAccept={accept} />}
    {modal === "outlook" && shared && <OutlookModal shared={shared} onClose={() => setModal(null)} onSend={() => { setModal(null); notify("Contact details sent to Noor through Outlook."); }} />}
    {toast && <div className="toast"><span><Icon name="check" size={16} /></span>{toast}<button onClick={() => setToast("")}><Icon name="close" size={15} /></button></div>}
  </div>;
}
