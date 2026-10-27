export default function AdminSearchBar({ value, onChange, placeholder = "Search" }) {
  return <input className="admin-search admin-search-reusable" value={value} onChange={(event) => onChange(event.target.value)} placeholder={placeholder} />;
}
