const API_BASE = import.meta.env.VITE_API_BASE || "";

export async function sendMessage(message, userProfile = {}) {
  const response = await fetch(`${API_BASE}/api/v1/chat`, { 
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      message,
      user_profile: userProfile,
    }),
  });

  return response.json();
}

async function parseResponse(response) {
  let payload = null;
  try {
    payload = await response.json();
  } catch (_err) {
    payload = null;
  }
  if (!response.ok || payload?.ok === false) {
    const message = payload?.error || payload?.message || `Request failed (${response.status})`;
    throw new Error(message);
  }
  return payload;
}

export async function extractProfile(formData) {
  const response = await fetch(`${API_BASE}/api/extract-profile`, {
    method: "POST",
    body: formData,
  });
  return parseResponse(response);
}

export async function generateAdvice(formData) {
  const response = await fetch(`${API_BASE}/api/advise`, {
    method: "POST",
    body: formData,
  });
  return parseResponse(response);
}

export async function getSettingsStatus() {
  const response = await fetch(`${API_BASE}/api/settings/status`);
  return parseResponse(response);
}

export async function saveSettings({ apiKey, model, baseUrl, action = "save" }) {
  const response = await fetch(`${API_BASE}/api/settings`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ api_key: apiKey, model, base_url: baseUrl, action }),
  });
  return parseResponse(response);
}