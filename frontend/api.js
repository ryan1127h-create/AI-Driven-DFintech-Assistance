const RAW_API_BASE = (import.meta.env.VITE_API_BASE || "").replace(/\/$/, "");
const API_BASE = RAW_API_BASE.endsWith("/api/v1") ? RAW_API_BASE : `${RAW_API_BASE}/api/v1`;

function buildUrl(path) {
  return `${API_BASE}${path}`;
}

function getAuthHeaders() {
  const token = localStorage.getItem("token");

  if (!token) {
    return {};
  }

  return { Authorization: `Bearer ${token}` };
}

// Fired when the server rejects the stored token (expired or revoked);
// RoleContext listens for it and signs the user out locally.
export const SESSION_EXPIRED_EVENT = "auth:session-expired";

async function handleResponse(response) {
  if (!response.ok) {
    if (response.status === 401 && localStorage.getItem("token")) {
      window.dispatchEvent(new Event(SESSION_EXPIRED_EVENT));
    }
    const error = await response.json().catch(() => ({}));

    throw new Error(
      error.detail || error.message || "Request failed"
    );
  }

  return response.json();
}

// Login 
export async function login(data) {
  const response = await fetch(buildUrl("/auth/login"), {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(data),
  });

  return handleResponse(response);
}

export async function logout(){
  const response = await fetch(buildUrl("/auth/logout"),{
    method: "POST",
    headers:{
      "Content-Type": "application/json",
      ...getAuthHeaders(),
    }
  });
  return handleResponse(response);
} 

// The logged-in user (role and lifecycle stage as the server sees them now).
export async function getMe() {
  const response = await fetch(buildUrl("/auth/me"), { headers: getAuthHeaders() });
  return handleResponse(response);
}

// Changes the user's display name; returns the refreshed user.
export function updateMe(fullName) {
  return jsonRequest("PATCH", "/auth/me", { full_name: fullName });
}

// Records that the user skipped or finished the profile welcome
// questionnaire ("skipped" | "completed"); returns the refreshed user.
export function setOnboardingStatus(status) {
  return jsonRequest("PUT", "/auth/onboarding", { status });
}

// Register — two steps: register() starts it and emails a 6-digit code (no
// account exists yet, no token), verifyEmail() completes it and logs the
// new account in (see backend/app/domains/auth/service.py).
export async function register(data) {
  const response = await fetch(buildUrl("/auth/register"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  return handleResponse(response);
}

export async function verifyEmail({ email, code }) {
  const response = await fetch(buildUrl("/auth/verify-email"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, code }),
  });
  return handleResponse(response);
}

export async function resendVerificationCode(email) {
  const response = await fetch(buildUrl("/auth/resend-code"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email }),
  });
  return handleResponse(response);
}

export async function sendMessage(message, extra = {}) {
  const response = await fetch(buildUrl("/chat"), {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...getAuthHeaders(),
    },
    body: JSON.stringify({
      message,
      session_id: extra.session_id,
    }),
  });

  return handleResponse(response);
}

// Streaming counterpart of sendMessage() — hits POST /chat/stream (SSE) and
// dispatches parsed events to the given callbacks as they arrive, instead of
// waiting for the whole reply. Native EventSource can't be used here (it
// only supports GET with no custom headers, and auth here is a POST body +
// Authorization header), so this parses the SSE wire format by hand off a
// fetch() ReadableStream — safe to do manually since we control both ends
// (this frontend and the FastAPI backend that generates these frames).
// A 423 means the conversation's earlier turns are being summarized in the
// background (a few seconds, every ~15 turns): wait the Retry-After the
// server sends and try again, up to this many times, before giving up.
const SUMMARIZING_RETRIES = 3;

export async function sendMessageStream(message, extra = {}, { onStep, onToken, onDone, onError } = {}) {
  const send = () => fetch(buildUrl("/chat/stream"), {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...getAuthHeaders(),
    },
    body: JSON.stringify({
      message,
      session_id: extra.session_id,
      // Card fields the user just skipped or dismissed (see backend
      // ChatRequest.declined_fields).
      declined_fields: extra.declined_fields || [],
    }),
  });

  let response = await send();
  for (let attempt = 0; response.status === 423 && attempt < SUMMARIZING_RETRIES; attempt += 1) {
    onStep?.({ type: "step", stage: "waiting_for_history" });
    const seconds = Number(response.headers.get("Retry-After")) || 5;
    await new Promise((resolve) => setTimeout(resolve, seconds * 1000));
    response = await send();
  }

  if (!response.ok) {
    // Pre-stream failures (e.g. 409/423 lock conflicts) — same error shape
    // as the non-streaming endpoints, so reuse handleResponse's parsing.
    return handleResponse(response);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });

    let separatorIndex;
    while ((separatorIndex = buffer.indexOf("\n\n")) !== -1) {
      const rawEvent = buffer.slice(0, separatorIndex);
      buffer = buffer.slice(separatorIndex + 2);

      const eventTypeMatch = rawEvent.match(/^event: (.+)$/m);
      const dataMatch = rawEvent.match(/^data: (.+)$/m);
      if (!dataMatch) continue;

      const type = eventTypeMatch ? eventTypeMatch[1] : "message";
      const data = JSON.parse(dataMatch[1]);

      if (type === "step") onStep?.(data);
      else if (type === "token") onToken?.(data.text);
      else if (type === "done") onDone?.(data);
      else if (type === "error") onError?.(data);
    }
  }
}

export async function getChatSessions() {
  const response = await fetch(buildUrl("/chat/sessions"), {
    headers: getAuthHeaders(),
  });

  return handleResponse(response);
}

// Requests to staff raised from the chat: the user's own list, and taking
// up the offer the latest reply made (POST /chat/{id}/escalations).
export function getMyEscalations() { return fetch(buildUrl("/chat/escalations"), { headers: getAuthHeaders() }).then(handleResponse); }
export function acceptEscalationOffer(sessionId) { return jsonRequest("POST", `/chat/${encodeURIComponent(sessionId)}/escalations`, {}); }

export async function getChatHistory(sessionId) {
  const response = await fetch(buildUrl(`/chat/${sessionId}/history`), {
    headers: getAuthHeaders(),
  });

  return handleResponse(response);
}

export async function rollbackChat(sessionId, turns) {
  const response = await fetch(buildUrl(`/chat/${sessionId}/rollback`), {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...getAuthHeaders(),
    },
    body: JSON.stringify({ turns }),
  });

  return handleResponse(response);
}

export async function clearChat(sessionId) {
  const response = await fetch(
    buildUrl(`/chat/${sessionId}`),
    {
      method: "DELETE",
      headers: getAuthHeaders(),
    }
  );

  return handleResponse(response);
}

function jsonRequest(method, path, body) {
  return fetch(buildUrl(path), {
    method,
    headers: { "Content-Type": "application/json", ...getAuthHeaders() },
    body: body === undefined ? undefined : JSON.stringify(body),
  }).then(handleResponse);
}

// Profile — field-dictionary based (see backend/app/domains/profile/api.py).
// GET /profile returns { user_id, fields: { key: { value, source, verified,
// updated_at, editable, locked_reason } }, open_conflicts }.

export async function getProfile() {
  const response = await fetch(buildUrl("/profile"), { headers: getAuthHeaders() });
  return handleResponse(response);
}

export async function getProfileDefinitions() {
  const response = await fetch(buildUrl("/profile/definitions"), { headers: getAuthHeaders() });
  return handleResponse(response);
}

// fields: { field_key: value } — a null value deletes the field.
// cvDocumentId: set when the answers were reviewed after a CV import, so
// the server can store unchanged CV values as coming from the CV.
export function updateProfile(fields, cvDocumentId) {
  return jsonRequest("PATCH", "/profile", cvDocumentId ? { fields, cv_document_id: cvDocumentId } : { fields });
}

// Uploads a PDF/DOCX CV; returns the checked candidates it yielded (see
// backend/app/domains/cv_import/). The browser sets the multipart
// Content-Type itself.
export async function importCv(file) {
  const body = new FormData();
  body.append("file", file);
  const response = await fetch(buildUrl("/cv-import"), { method: "POST", headers: getAuthHeaders(), body });
  return handleResponse(response);
}

// Forgets what was kept from the user's CVs (details found and the lines
// they came from); values already on the profile stay.
export function deleteCvData() {
  return jsonRequest("DELETE", "/cv-import");
}

// Assistant preferences: { language_pref: ["en", ...], answer_depth:
// "concise" | "standard" | "detailed", email_notifications }.
export async function getSettings() {
  const response = await fetch(buildUrl("/auth/settings"), { headers: getAuthHeaders() });
  return handleResponse(response);
}

export function updateSettings(changes) {
  return jsonRequest("PATCH", "/auth/settings", changes);
}

// The user's most recent CV import, or null.
export async function getLatestCvImport() {
  const response = await fetch(buildUrl("/cv-import/latest"), { headers: getAuthHeaders() });
  return handleResponse(response);
}

export async function getProfileConflicts() {
  const response = await fetch(buildUrl("/profile/conflicts"), { headers: getAuthHeaders() });
  return handleResponse(response);
}

// action: "accept_candidate" | "keep_current" | "dismiss"
export function resolveProfileConflict(conflictId, action) {
  return jsonRequest("POST", `/profile/conflicts/${conflictId}`, { action });
}

export async function getConsents() {
  const response = await fetch(buildUrl("/profile/consents"), { headers: getAuthHeaders() });
  return handleResponse(response);
}

// consents: { consent_key: boolean }
export function updateConsents(consents) {
  return jsonRequest("PUT", "/profile/consents", { consents });
}

export async function getChecklist() {
  const response = await fetch(buildUrl("/checklist"), {
    headers: getAuthHeaders(),
  });
  return handleResponse(response);
}

// The current student's academic record, course enrollments and degree
// progress — current/graduating students only (403 otherwise).
export async function getLifecycle() {
  const response = await fetch(buildUrl("/lifecycle"), { headers: getAuthHeaders() });
  return handleResponse(response);
}


// Binds the admission application filed under the user's login email to
// their account; returns the refreshed checklist.
export function bindApplication(applicationNo) {
  return jsonRequest("POST", "/checklist/application", { application_no: applicationNo });
}

// ---------------------------------------------------------------------------
// Admin escalation cases
// ---------------------------------------------------------------------------
// GET /admin/escalations returns every case with { items, total, stats };
// the page filters and paginates them itself.

export async function getAdminEscalationCases() {
  const response = await fetch(buildUrl("/admin/escalations"), {
    headers: getAuthHeaders(),
  });
  return handleResponse(response);
}

export async function getAdminEscalationCase(caseId) {
  const response = await fetch(buildUrl(`/admin/escalations/${encodeURIComponent(caseId)}`), {
    headers: getAuthHeaders(),
  });
  return handleResponse(response);
}

export function updateAdminEscalationCase(caseId, updates) {
  return jsonRequest("PATCH", `/admin/escalations/${encodeURIComponent(caseId)}`, updates);
}

export async function getAdminOverview() {
  const response = await fetch(buildUrl("/admin/overview"), {
    headers: getAuthHeaders(),
  });
  return handleResponse(response);
}

export function getAdminUsers(search = "") {
  const query = search ? `?search=${encodeURIComponent(search)}` : "";
  return fetch(buildUrl(`/admin/users${query}`), { headers: getAuthHeaders() }).then(handleResponse);
}

export function getAdminUser(userId) {
  return fetch(buildUrl(`/admin/users/${encodeURIComponent(userId)}`), { headers: getAuthHeaders() }).then(handleResponse);
}

export function updateAdminUser(userId, changes) {
  return jsonRequest("PATCH", `/admin/users/${encodeURIComponent(userId)}`, changes);
}

export function deleteAdminUser(userId) {
  return fetch(buildUrl(`/admin/users/${encodeURIComponent(userId)}`), { method: "DELETE", headers: getAuthHeaders() }).then(handleResponse);
}

export function getAdminApplications() { return fetch(buildUrl("/admin/applications"), { headers: getAuthHeaders() }).then(handleResponse); }
export function getAdminApplication(id) { return fetch(buildUrl(`/admin/applications/${encodeURIComponent(id)}`), { headers: getAuthHeaders() }).then(handleResponse); }
export function updateAdminApplication(id, changes) { return jsonRequest("PATCH", `/admin/applications/${encodeURIComponent(id)}`, changes); }
export function updateAdminChecklistItem(id, submitted) { return jsonRequest("PATCH", `/admin/checklist/${encodeURIComponent(id)}`, { submitted }); }
export function deleteAdminApplication(id) { return fetch(buildUrl(`/admin/applications/${encodeURIComponent(id)}`), { method: "DELETE", headers: getAuthHeaders() }).then(handleResponse); }
export function getAdminConversations() { return fetch(buildUrl("/admin/conversations"), { headers: getAuthHeaders() }).then(handleResponse); }
export function getAdminConversation(id) { return fetch(buildUrl(`/admin/conversations/${encodeURIComponent(id)}`), { headers: getAuthHeaders() }).then(handleResponse); }
export function getAdminKnowledge(search = "", mainTable = "all") { const params = new URLSearchParams(); if (search) params.set("search", search); if (mainTable !== "all") params.set("main_table", mainTable); const query = params.toString() ? `?${params}` : ""; return fetch(buildUrl(`/admin/knowledge${query}`), { headers: getAuthHeaders() }).then(handleResponse); }
export function updateAdminKnowledge(category, id, changes) { return jsonRequest("PATCH", `/admin/knowledge/${encodeURIComponent(category)}/${encodeURIComponent(id)}`, changes); }
export function getAdminKnowledgeCourse(courseCode) { return fetch(buildUrl(`/admin/knowledge/courses/${encodeURIComponent(courseCode)}`), { headers: getAuthHeaders() }).then(handleResponse); }
export function getAdminKnowledgeProgram(programId) { return fetch(buildUrl(`/admin/knowledge/programs/${encodeURIComponent(programId)}`), { headers: getAuthHeaders() }).then(handleResponse); }
export function updateAdminKnowledgeProgram(programId, changes) { return jsonRequest("PATCH", `/admin/knowledge/programs/${encodeURIComponent(programId)}`, changes); }
export function updateAdminKnowledgeCourse(courseCode, changes) { return jsonRequest("PATCH", `/admin/knowledge/courses/${encodeURIComponent(courseCode)}`, changes); }
export function updateAdminKnowledgeCourseRelated(courseCode, relation, row) { return jsonRequest("PATCH", `/admin/knowledge/courses/${encodeURIComponent(courseCode)}/${encodeURIComponent(relation)}`, { row }); }

// PATCH /admin/escalations/{id} only resolves a case, with optional notes.
export function resolveAdminEscalationCase(caseId, resolutionNotes) {
  return jsonRequest("PATCH", `/admin/escalations/${encodeURIComponent(caseId)}`, {
    status: "Resolved",
    ...(resolutionNotes && { resolution_notes: resolutionNotes }),
  });
}

// ---------------------------------------------------------------------------
// Alumni matching
// ---------------------------------------------------------------------------
// Enrolled students browse listed alumni and send requests; alumni answer
// them. Contact details only appear once a request is accepted.

export function getAlumniMe() { return fetch(buildUrl("/alumni/me"), { headers: getAuthHeaders() }).then(handleResponse); }
export function setAlumniListed(listed) { return jsonRequest("PATCH", "/alumni/me", { listed }); }

export function getAlumniMatches({ search = "", expertise = [] } = {}) {
  const params = new URLSearchParams();
  if (search) params.set("search", search);
  if (expertise.length) params.set("expertise", expertise.join(","));
  const query = params.toString() ? `?${params}` : "";
  return fetch(buildUrl(`/alumni/matches${query}`), { headers: getAuthHeaders() }).then(handleResponse);
}

export function getAlumniRequests() { return fetch(buildUrl("/alumni/requests"), { headers: getAuthHeaders() }).then(handleResponse); }
export function createAlumniRequest({ alumniId, note = "" }) { return jsonRequest("POST", "/alumni/requests", { alumni_id: alumniId, note: note || null }); }
export function acceptAlumniRequest(requestId, { share = [], replyNote = "" } = {}) { return jsonRequest("PATCH", `/alumni/requests/${encodeURIComponent(requestId)}`, { action: "accept", share, reply_note: replyNote || null }); }
export function declineAlumniRequest(requestId) { return jsonRequest("PATCH", `/alumni/requests/${encodeURIComponent(requestId)}`, { action: "decline" }); }
export function cancelAlumniRequest(requestId) { return jsonRequest("PATCH", `/alumni/requests/${encodeURIComponent(requestId)}`, { action: "cancel" }); }

// Staff: the alumni directory.
export function getAdminAlumni() { return fetch(buildUrl("/admin/alumni"), { headers: getAuthHeaders() }).then(handleResponse); }
export function createAdminAlumnus(fields) { return jsonRequest("POST", "/admin/alumni", fields); }
export function updateAdminAlumnus(userId, fields) { return jsonRequest("PATCH", `/admin/alumni/${encodeURIComponent(userId)}`, fields); }
export function deleteAdminAlumnus(userId) { return fetch(buildUrl(`/admin/alumni/${encodeURIComponent(userId)}`), { method: "DELETE", headers: getAuthHeaders() }).then(handleResponse); }
