import { useEffect, useMemo, useState } from "react"
import { getAdminEscalationCases, resolveAdminEscalationCase } from "../../api"
import { PageHeader } from "../components/student/PageParts"

function FeatureButton({ children, variant = "primary", className = "", ...props }) {
  return <button className={`feature-button feature-button-${variant} ${className}`.trim()} {...props}>{children}</button>
}

function Icon({ name, size = 18 }) {
  const paths = {
    dashboard: (
      <>
        <rect x="3" y="3" width="7" height="7" rx="1" />
        <rect x="14" y="3" width="7" height="7" rx="1" />
        <rect x="3" y="14" width="7" height="7" rx="1" />
        <rect x="14" y="14" width="7" height="7" rx="1" />
      </>
    ),
    cases: (
      <>
        <path d="M9 5h10a2 2 0 0 1 2 2v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2h4" />
        <path d="M9 3h6v4H9zM8 12h8M8 16h5" />
      </>
    ),
    users: (
      <>
        <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" />
        <circle cx="9" cy="7" r="4" />
        <path d="M22 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75" />
      </>
    ),
    book: (
      <>
        <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
        <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" />
      </>
    ),
    analytics: (
      <>
        <path d="M4 19V9M10 19V5M16 19v-7M22 19H2" />
      </>
    ),
    settings: (
      <>
        <circle cx="12" cy="12" r="3" />
        <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06-2.83 2.83-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21h-4v-.09a1.65 1.65 0 0 0-1.08-1.5 1.65 1.65 0 0 0-1.82.33l-.06.06-2.83-2.83.06-.06A1.65 1.65 0 0 0 4.6 15a1.65 1.65 0 0 0-1.51-1H3v-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06 2.83-2.83.06.06A1.65 1.65 0 0 0 9 4.6a1.65 1.65 0 0 0 1-1.51V3h4v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06 2.83 2.83-.06.06A1.65 1.65 0 0 0 19.4 9c.12.61.66 1.05 1.29 1.05H21v4h-.09A1.65 1.65 0 0 0 19.4 15z" />
      </>
    ),
    bell: (
      <>
        <path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M13.73 21a2 2 0 0 1-3.46 0" />
      </>
    ),
    search: (
      <>
        <circle cx="11" cy="11" r="7" />
        <path d="m20 20-4-4" />
      </>
    ),
    chevron: <path d="m8 10 4 4 4-4" />,
    arrow: <path d="m9 18 6-6-6-6" />,
    mail: (
      <>
        <rect x="3" y="5" width="18" height="14" rx="2" />
        <path d="m3 7 9 6 9-6" />
      </>
    ),
    clock: (
      <>
        <circle cx="12" cy="12" r="9" />
        <path d="M12 7v5l3 2" />
      </>
    ),
    close: (
      <>
        <path d="m6 6 12 12M18 6 6 18" />
      </>
    ),
    check: <path d="m5 12 4 4L19 6" />,
    user: (
      <>
        <circle cx="12" cy="8" r="4" />
        <path d="M4 21a8 8 0 0 1 16 0" />
      </>
    ),
    filter: <path d="M4 6h16M7 12h10M10 18h4" />,
  }
  return (
    <svg
      aria-hidden="true"
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      {paths[name]}
    </svg>
  )
}

function Badge({ children, tone = "neutral" }) {
  return <span className={`badge badge-${tone}`}>{children}</span>
}

function Select({
  label,
  value,
  onChange,
  children
}) {
  return (
    <label className="select-wrap">
      <span className="sr-only">{label}</span>
      <select value={value} onChange={(event) => onChange(event.target.value)}>
        {children}
      </select>
      <Icon name="chevron" size={15} />
    </label>
  )
}

function KpiCard({
  label,
  value,
  icon,
  tone,
  helper
}) {
  return (
    <div className={`kpi-card kpi-${tone}`}>
      <div className="kpi-top">
        <span className="kpi-label">{label}</span>
        <span className="kpi-icon">
          <Icon name={icon} size={17} />
        </span>
      </div>
      <div className="kpi-value">{value}</div>
      <div className="kpi-helper">{helper}</div>
    </div>
  )
}

function mailto(caseItem) {
  return `mailto:${caseItem.email}?subject=${encodeURIComponent(`Follow-up regarding your support request – Case #${caseItem.shortId}`)}`
}

function CaseDrawer({
  caseItem,
  onClose,
  onResolve
}) {
  return (
    <>
      <div className="drawer-scrim" onClick={onClose} />
      <aside className="drawer" aria-label={`Case ${caseItem.shortId} details`}>
        <div className="drawer-header">
          <div>
            <div className="eyebrow">ESCALATION CASE</div>
            <div className="drawer-title">Case #{caseItem.shortId}</div>
            <div className="drawer-badges">
              <Badge
                tone={caseItem.priority === "Urgent" ? "urgent" : "normal"}
              >
                {caseItem.priority.toUpperCase()}
              </Badge>
              <Badge
                tone={caseItem.status === "Resolved" ? "resolved" : "open"}
              >
                {caseItem.status.toUpperCase()}
              </Badge>
            </div>
          </div>
          <FeatureButton variant="icon" onClick={onClose} title="Close case details">
            <Icon name="close" />
          </FeatureButton>
        </div>

        <div className="drawer-content">
          <section className="detail-section">
            <div className="section-title">Case Information</div>
            <div className="info-grid">
              <Info label="Case ID" value={caseItem.id} wide mono />
              <Info label="Category" value={caseItem.category} />
              <Info
                label="Priority"
                value={caseItem.priority}
                accent={caseItem.priority === "Urgent"}
              />
              <Info label="Status" value={caseItem.status} />
              <Info label="Trigger Source" value={caseItem.trigger} />
              <Info
                label="Origin Specialist"
                value={`${caseItem.origin} Agent`}
              />
              <Info
                label="Created"
                value={`${caseItem.createdDate}, ${caseItem.createdTime}`}
              />
              <Info label="Resolved At" value={caseItem.resolvedAt ?? "—"} />
            </div>
          </section>

          <section className="detail-section">
            <div className="section-title">User Information</div>
            <div className="user-card">
              <div className="avatar avatar-large">{caseItem.initials}</div>
              <div className="user-card-info">
                <strong>{caseItem.name}</strong>
                <a href={mailto(caseItem)}>{caseItem.email}</a>
              </div>
              <div className="user-actions">
                <a className="button button-primary" href={mailto(caseItem)}>
                  <Icon name="mail" size={16} />
                  Reply via Outlook
                </a>
                <FeatureButton variant="secondary">
                  <Icon name="user" size={16} />
                  View User Profile
                </FeatureButton>
              </div>
            </div>
          </section>

          <section className="detail-section summary-section">
            <div className="section-title">Escalation Summary</div>
            <div className="summary-card">{caseItem.summary}</div>
          </section>

          <section className="detail-section">
            <div className="section-title">Escalation Context</div>
            <div className="context-row">
              <span>Triggered by</span>
              <strong>{caseItem.trigger} escalation</strong>
            </div>
            <div className="context-row">
              <span>Origin Specialist</span>
              <strong>{caseItem.origin} Agent</strong>
            </div>
            <div className="context-row">
              <span>Category</span>
              <strong>{caseItem.category}</strong>
            </div>
            <div className="context-note">
              <span className="context-note-icon">
                <Icon name="cases" size={16} />
              </span>
              This case was escalated because the AI specialist had insufficient
              confidence to provide a reliable answer.
            </div>
          </section>

          <section className="detail-section resolution-section">
            <div className="section-title">Resolution</div>
            {caseItem.status === "Resolved" ? (
              <div className="resolved-panel">
                <div className="resolved-heading">
                  <span>
                    <Icon name="check" size={16} />
                  </span>
                  Resolved
                </div>
                <div className="resolved-meta">
                  Resolved by: <strong>{caseItem.resolvedBy}</strong>
                </div>
                <div className="resolved-meta">
                  Resolved at: <strong>{caseItem.resolvedAt}</strong>
                </div>
                <div className="resolution-label">Resolution Notes</div>
                <div className="resolution-copy">
                  {caseItem.resolutionNotes}
                </div>
                <FeatureButton disabled className="full-width">
                  <Icon name="check" size={16} />
                  Mark as Resolved
                </FeatureButton>
              </div>
            ) : (
              <>
                <label className="notes-label" htmlFor="resolution-notes">
                  Resolution Notes
                </label>
                <textarea
                  id="resolution-notes"
                  placeholder="Add internal notes about how this case was handled..."
                />
                <div className="resolution-footer">
                  <span>Only admins can view these notes.</span>
                  <FeatureButton onClick={onResolve}>
                    <Icon name="check" size={16} />
                    Mark as Resolved
                  </FeatureButton>
                </div>
              </>
            )}
          </section>
        </div>
      </aside>
    </>
  )
}

function Info({
  label,
  value,
  wide,
  mono,
  accent
}) {
  return (
    <div className={`info-item ${wide ? "info-wide" : ""}`}>
      <span>{label}</span>
      <strong className={`${mono ? "mono" : ""} ${accent ? "accent" : ""}`}>
        {value}
      </strong>
    </div>
  )
}

function ResolveModal({
  onCancel,
  onConfirm
}) {
  return (
    <div
      className="modal-layer"
      role="dialog"
      aria-modal="true"
      aria-labelledby="resolve-title"
    >
      <div className="modal">
        <div className="modal-icon">
          <Icon name="check" size={24} />
        </div>
        <div className="modal-title" id="resolve-title">
          Resolve this case?
        </div>
        <div className="modal-copy">
          This case will be marked as resolved and the resolution time and admin
          responsible will be recorded.
        </div>
        <div className="modal-actions">
          <FeatureButton variant="secondary" onClick={onCancel}>
            Cancel
          </FeatureButton>
          <FeatureButton onClick={onConfirm}>Mark as Resolved</FeatureButton>
        </div>
      </div>
    </div>
  )
}

function LoadingRows() {
  return (
    <>
      {[1, 2, 3, 4, 5].map((row) => (
        <tr className="skeleton-row" key={row}>
          <td>
            <span />
          </td>
          <td>
            <span />
          </td>
          <td>
            <span className="skeleton-wide" />
          </td>
          <td>
            <span />
          </td>
          <td>
            <span />
          </td>
          <td>
            <span />
          </td>
          <td>
            <span />
          </td>
          <td>
            <span />
          </td>
          <td>
            <span />
          </td>
        </tr>
      ))}
    </>
  )
}

export default function App() {
  const [isLoading, setIsLoading] = useState(true)
  const [search, setSearch] = useState("")
  const [status, setStatus] = useState("All")
  const [priority, setPriority] = useState("All")
  const [category, setCategory] = useState("All Categories")
  const [source, setSource] = useState("All Sources")
  const [specialist, setSpecialist] = useState("All Specialists")
  const [date, setDate] = useState("All Time")
  const [sort, setSort] = useState("Newest")
  const [selected, setSelected] = useState(null)
  const [resolveConfirm, setResolveConfirm] = useState(false)
  const [caseData, setCaseData] = useState([])
  const [stats, setStats] = useState({ open_cases: 0, urgent_cases: 0, resolved_today: 0, avg_resolution_time: "0h 00m" })

  useEffect(() => {
    let active = true
    getAdminEscalationCases().then(({ items, stats: nextStats }) => {
      if (!active) return
      setCaseData(items)
      setStats(nextStats || stats)
      setIsLoading(false)
    })
    return () => { active = false }
  }, [])

  const filteredCases = useMemo(() => {
    const query = search.toLowerCase()
    let result = caseData.filter((item) => {
      const matchesSearch =
        !query ||
        `${item.shortId} ${item.name} ${item.email} ${item.summary}`
          .toLowerCase()
          .includes(query)
      return (
        matchesSearch &&
        (status === "All" || item.status === status) &&
        (priority === "All" || item.priority === priority) &&
        (category === "All Categories" || item.category === category) &&
        (source === "All Sources" || item.trigger === source) &&
        (specialist === "All Specialists" || item.origin === specialist)
      )
    })
    if (sort === "Priority")
      result = [...result].sort(
        (a, b) =>
          Number(b.priority === "Urgent") - Number(a.priority === "Urgent"),
      )
    if (sort === "Oldest") result = [...result].reverse()
    return result
  }, [search, status, priority, category, source, specialist, sort, caseData])

  const resetFilters = () => {
    setSearch("")
    setStatus("All")
    setPriority("All")
    setCategory("All Categories")
    setSource("All Sources")
    setSpecialist("All Specialists")
    setDate("All Time")
    setSort("Newest")
  }

  const confirmResolve = () => {
    if (!selected) return
    resolveAdminEscalationCase(selected.id, "Resolved by admin").then((resolved) => {
      setCaseData((items) => items.map((item) => (item.id === resolved.id ? resolved : item)))
      setSelected(resolved)
      setResolveConfirm(false)
    })
  }

  return (
    <div className="admin-escalation-content">

      <main className="admin-escalation-main">

        <div className="content">
          <PageHeader
            title="Escalation Cases"
            subtitle="Review and manage cases escalated by the AI assistant."
            className="admin-shared-page-header"
          />
          <div className="kpi-grid">
            <KpiCard
              label="Open Cases"
              value={stats.open_cases}
              helper="Live from Supabase"
              icon="cases"
              tone="blue"
            />
            <KpiCard
              label="Urgent Cases"
              value={stats.urgent_cases}
              helper="Live from Supabase"
              icon="bell"
              tone="orange"
            />
            <KpiCard
              label="Resolved Today"
              value={stats.resolved_today}
              helper="Resolved today"
              icon="check"
              tone="green"
            />
            <KpiCard
              label="Avg. Resolution Time"
              value={stats.avg_resolution_time}
              helper="Across resolved cases"
              icon="clock"
              tone="purple"
            />
          </div>

          <section className="table-card">
            <div className="toolbar">
              <div className="search-wrap">
                <Icon name="search" size={18} />
                <input
                  aria-label="Search cases"
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                  placeholder="Search by case ID, user email, or summary..."
                />
              </div>
              <div className="toolbar-count">
                <strong>{filteredCases.length || 0}</strong> visible cases
              </div>
            </div>
            <div className="filters">
              <div className="filter-icon">
                <Icon name="filter" size={17} />
              </div>
              <Select label="Status" value={status} onChange={setStatus}>
                <option>All</option>
                <option>Open</option>
                <option>Resolved</option>
              </Select>
              <Select label="Priority" value={priority} onChange={setPriority}>
                <option>All</option>
                <option>Normal</option>
                <option>Urgent</option>
              </Select>
              <Select label="Category" value={category} onChange={setCategory}>
                <option>All Categories</option>
                <option>Policy Exception</option>
                <option>Complaint</option>
                <option>Low Confidence</option>
                <option>Sensitive</option>
                <option>Explicit Request</option>
              </Select>
              <Select
                label="Trigger source"
                value={source}
                onChange={setSource}
              >
                <option>All Sources</option>
                <option>Direct</option>
                <option>Chained</option>
              </Select>
              <Select
                label="Origin specialist"
                value={specialist}
                onChange={setSpecialist}
              >
                <option>All Specialists</option>
                <option>Admission</option>
                <option>Career Planning</option>
                <option>Course Recommendation</option>
                <option>Other</option>
              </Select>
              <Select label="Date" value={date} onChange={setDate}>
                <option>All Time</option>
                <option>Today</option>
                <option>Last 7 Days</option>
                <option>Last 30 Days</option>
                <option>Custom Range</option>
              </Select>
              <FeatureButton variant="ghost" onClick={resetFilters}>
                Reset
              </FeatureButton>
              <div className="sort-control">
                <span>Sort by:</span>
                <Select label="Sort" value={sort} onChange={setSort}>
                  <option>Newest</option>
                  <option>Oldest</option>
                  <option>Priority</option>
                </Select>
              </div>
            </div>

            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>Priority</th>
                    <th>Case ID</th>
                    <th>User</th>
                    <th>Category</th>
                    <th>Origin</th>
                    <th>Trigger</th>
                    <th>Created</th>
                    <th>Status</th>
                    <th>
                      <span className="sr-only">Actions</span>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {isLoading ? (
                    <LoadingRows />
                  ) : (
                    filteredCases.map((item) => (
                      <tr
                        key={item.id}
                        className={
                          item.priority === "Urgent" && item.status === "Open"
                            ? "urgent-row"
                            : ""
                        }
                      >
                        <td>
                          <Badge
                            tone={
                              item.priority === "Urgent" ? "urgent" : "normal"
                            }
                          >
                            <span className="badge-dot" />
                            {item.priority}
                          </Badge>
                        </td>
                        <td>
                          <button
                            type="button"
                            className="case-link"
                            onClick={() => setSelected(item)}
                          >
                            #{item.shortId}
                          </button>
                        </td>
                        <td>
                          <div className="table-user">
                            <div className="avatar">{item.initials}</div>
                            <div>
                              <strong>{item.name}</strong>
                              <a href={mailto(item)}>{item.email}</a>
                            </div>
                          </div>
                        </td>
                        <td>{item.category}</td>
                        <td>{item.origin}</td>
                        <td>
                          <Badge tone="outline">{item.trigger}</Badge>
                        </td>
                        <td>
                          <div className="date-cell">
                            <strong>{item.createdDate}</strong>
                            <span>{item.createdTime}</span>
                          </div>
                        </td>
                        <td>
                          <Badge
                            tone={
                              item.status === "Resolved" ? "resolved" : "open"
                            }
                          >
                            <span className="badge-dot" />
                            {item.status}
                          </Badge>
                        </td>
                        <td>
                          <FeatureButton
                            variant="secondary"
                            className="view-button"
                            onClick={() => setSelected(item)}
                          >
                            View details
                            <Icon name="arrow" size={15} />
                          </FeatureButton>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
              {!isLoading && filteredCases.length === 0 && (
                <div className="empty-state">
                  <div className="empty-icon">
                    <Icon name="search" size={23} />
                  </div>
                  <strong>No escalation cases found.</strong>
                  <span>Try changing or clearing your filters.</span>
                  <FeatureButton variant="secondary" onClick={resetFilters}>
                    Clear all filters
                  </FeatureButton>
                </div>
              )}
            </div>

            <div className="pagination">
              <span>
                Showing <strong>1–20</strong> of <strong>124</strong> cases
              </span>
              <div className="page-buttons">
                <FeatureButton variant="secondary" disabled>
                  <Icon name="arrow" size={14} /> Previous
                </FeatureButton>
                <FeatureButton variant="primary">1</FeatureButton>
                <FeatureButton variant="secondary">2</FeatureButton>
                <FeatureButton variant="secondary">3</FeatureButton>
                <span>…</span>
                <FeatureButton variant="secondary">7</FeatureButton>
                <FeatureButton variant="secondary">
                  Next <Icon name="arrow" size={14} />
                </FeatureButton>
              </div>
            </div>
          </section>
        </div>
      </main>

      {selected && (
        <CaseDrawer
          caseItem={selected}
          onClose={() => setSelected(null)}
          onResolve={() => setResolveConfirm(true)}
        />
      )}
      {resolveConfirm && (
        <ResolveModal
          onCancel={() => setResolveConfirm(false)}
          onConfirm={confirmResolve}
        />
      )}
    </div>
  )
}





