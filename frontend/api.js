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
export async function sendMessageStream(message, extra = {}, { onStep, onToken, onDone, onError } = {}) {
  const response = await fetch(buildUrl("/chat/stream"), {
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
