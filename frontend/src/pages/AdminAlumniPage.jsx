/* eslint-disable react/prop-types */
import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { createAdminAlumnus, deleteAdminAlumnus, getAdminAlumni, updateAdminAlumnus } from "../../api";
import AdminLoadingState from "../components/admin/AdminLoadingState";
import AdminSearchBar from "../components/admin/AdminSearchBar";

// Staff maintain the alumni directory; each alumnus decides themself whether
// to be listed, so staff can hide an entry but never list it.
const EMPTY = { email: "", position: "", company: "", class_year: "", expertise: [], bio: "", photo_url: "", contact_email: "", contact_phone: "", linkedin_url: "" };
const TEXT_FIELDS = [["position", "Position *"], ["company", "Company *"], ["class_year", "Class of"], ["contact_email", "Contact email"], ["contact_phone", "Contact phone"], ["linkedin_url", "LinkedIn URL"], ["photo_url", "Photo URL"]];

function toForm(item) {
  return { ...EMPTY, ...Object.fromEntries(Object.keys(EMPTY).map((key) => [key, item[key] ?? EMPTY[key]])), expertise: item.expertise.map((tag) => tag.tag), class_year: item.class_year ?? "" };
}

function toPayload(form) {
  const payload = { ...form, class_year: form.class_year === "" ? null : Number(form.class_year) };
  delete payload.email;
  return payload;
}

function AlumnusForm({ initial, options, isNew, onCancel, onSave, saving, error }) {
  const [form, setForm] = useState(initial);
  const set = (key, value) => setForm((current) => ({ ...current, [key]: value }));
  const toggle = (tag) => set("expertise", form.expertise.includes(tag) ? form.expertise.filter((t) => t !== tag) : [...form.expertise, tag]);
  return <form className="admin-card admin-course-form" onSubmit={(event) => { event.preventDefault(); onSave(form); }}>
    <h2>{isNew ? "Add an alumnus" : `Edit ${initial.name || initial.email}`}</h2>
    {isNew && <label>Account email *<input type="email" required value={form.email} onChange={(e) => set("email", e.target.value)} placeholder="The email they log in with" /></label>}
    {isNew && <p className="admin-subline">The account becomes an alumnus (lifecycle stage “alumni”). The entry starts hidden; they choose to be listed themselves.</p>}
    {TEXT_FIELDS.map(([key, label]) => <label key={key}>{label}<input value={form[key]} type={key === "class_year" ? "number" : "text"} required={key === "position" || key === "company"} onChange={(e) => set(key, e.target.value)} /></label>)}
    <label>Bio<textarea value={form.bio} maxLength={2000} onChange={(e) => set("bio", e.target.value)} /></label>
    <fieldset><legend>Expertise</legend>{options.map((o) => <label className="admin-checkbox" key={o.tag}><input type="checkbox" checked={form.expertise.includes(o.tag)} onChange={() => toggle(o.tag)} /> {o.label}</label>)}</fieldset>
    {error && <p role="alert">{error}</p>}
    <div className="admin-profile-actions"><button type="button" className="admin-secondary-button" onClick={onCancel}>Cancel</button><button type="submit" className="admin-primary-button" disabled={saving}>{saving ? "Saving…" : "Save"}</button></div>
  </form>;
}

export default function AdminAlumniPage() {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [editing, setEditing] = useState(null); // "new" | item
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState("");
  const [message, setMessage] = useState("");
  const load = useCallback(() => getAdminAlumni().then((d) => { setData(d); setError(""); }).catch((e) => setError(e.message)), []);
  useEffect(() => { load(); }, [load]);

  const items = useMemo(() => {
    const query = search.trim().toLowerCase();
    return (data?.items || []).filter((item) => !query || `${item.name} ${item.email} ${item.position} ${item.company}`.toLowerCase().includes(query));
  }, [data, search]);

  const save = async (form) => {
    setSaving(true); setFormError("");
    try {
      if (editing === "new") await createAdminAlumnus({ email: form.email, ...toPayload(form) });
      else await updateAdminAlumnus(editing.user_id, toPayload(form));
      await load();
      setMessage(editing === "new" ? "Alumnus added. Their entry stays hidden until they list themselves." : "Changes saved.");
      setEditing(null);
    } catch (e) { setFormError(e.message); } finally { setSaving(false); }
  };
  const hide = async (item) => {
    try { await updateAdminAlumnus(item.user_id, { listed: false }); setMessage(`${item.name || item.email} is now hidden from students.`); await load(); } catch (e) { setMessage(e.message); }
  };
  const remove = async (item) => {
    if (!window.confirm(`Remove ${item.name || item.email} from the alumni directory? Their connection requests are deleted too. Their account stays.`)) return;
    try { await deleteAdminAlumnus(item.user_id); setMessage("Removed from the directory."); await load(); } catch (e) { setMessage(e.message); }
  };

  if (error) return <main className="admin-overview-page"><p role="alert">{error}</p></main>;
  if (!data) return <AdminLoadingState label="Loading alumni directory…" />;
  return <main className="admin-overview-page">
    <header className="admin-shared-page-header"><h1>Alumni</h1><p>Maintain the alumni directory students see in Alumni Match.</p></header>
    {message && <p role="status" className="admin-subline">{message}</p>}
    {editing ? <AlumnusForm key={editing === "new" ? "new" : editing.user_id} initial={editing === "new" ? EMPTY : { ...toForm(editing), name: editing.name, email: editing.email }} options={data.expertise_options} isNew={editing === "new"} saving={saving} error={formError} onCancel={() => setEditing(null)} onSave={save} />
      : <section className="admin-card admin-conversation-filter"><AdminSearchBar placeholder="Search alumni" value={search} onChange={setSearch} /><button type="button" className="admin-primary-button" onClick={() => { setFormError(""); setMessage(""); setEditing("new"); }}>Add alumnus</button></section>}
    <section className="admin-card admin-table-wrap"><table><thead><tr><th>Name</th><th>Position</th><th>Expertise</th><th>Listed</th><th>Actions</th></tr></thead><tbody>
      {items.length ? items.map((item) => <tr key={item.user_id}>
        <td><Link className="admin-related-link" to={`/admin/users/${item.user_id}`}>{item.name || item.email}</Link><br /><small>{item.email}</small></td>
        <td>{item.position} · {item.company}{item.class_year ? ` · ${item.class_year}` : ""}</td>
        <td>{item.expertise.map((tag) => tag.label).join(", ") || "—"}</td>
        <td>{item.listed ? "Listed" : "Hidden"}</td>
        <td><button type="button" className="admin-table-action" onClick={() => { setFormError(""); setMessage(""); setEditing(item); }}>Edit</button>{item.listed && <button type="button" className="admin-table-action" onClick={() => hide(item)}>Hide</button>}<button type="button" className="admin-table-action" onClick={() => remove(item)}>Remove</button></td>
      </tr>) : <tr><td colSpan="5">{data.items.length ? "No alumni match your search." : "No alumni in the directory yet."}</td></tr>}
    </tbody></table></section>
  </main>;
}
