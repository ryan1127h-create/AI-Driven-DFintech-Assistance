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

async function handleResponse(response) {
  if (!response.ok) {
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

// Register
export async function register(data) {
  const response = await fetch(buildUrl("/auth/register"),{
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(data),
    }
  );

  const result = await response.json();

  if (!response.ok) {
    throw new Error(JSON.stringify(result));
  }

  return result;
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

export async function recommendCourses(payload = {}) {
  const response = await fetch(buildUrl("/course-recommendations"), {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...getAuthHeaders(),
    },
    body: JSON.stringify(payload),
  });

  return handleResponse(response);
}

export async function comparePrograms(payload = {}) {
  const response = await fetch(buildUrl("/program-comparisons"), {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...getAuthHeaders(),
    },
    body: JSON.stringify(payload),
  });

  return handleResponse(response);
}

export async function createCareerPlan(payload = {}) {
  const response = await fetch(buildUrl("/career-plans"), {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...getAuthHeaders(),
    },
    body: JSON.stringify(payload),
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

export async function extractProfile(formData) {
  const lifecycle = formData?.lifecycle_stage === "current" ? "enrolled" : "applicant";
  const cvFile = formData?.cvFile || null;

  if (!cvFile) {
    return {
      prefill: {
        lifecycle_stage: formData?.lifecycle_stage || "applicant",
        profile_summary: formData?.text || "",
      },
    };
  }

  const uploadData = new FormData();
  uploadData.append("file", cvFile);
  const uploadResponse = await fetch(buildUrl("/checklist/items/cv/file"), {
    method: "POST",
    headers: getAuthHeaders(),
    body: uploadData,
  });
  await handleResponse(uploadResponse);

  const response = await fetch(buildUrl("/profile/resume"), {
    method: "POST",
    headers: getAuthHeaders(),
  });

  const profile = await handleResponse(response);

  return {
    prefill: {
      lifecycle_stage:
        profile.lifecycle_stage === "applicant" ? "applicant" : "prospect",
      degree_level: "",
      field_of_study: profile.academic_background_std || "",
      academic_background_std: profile.academic_background_std || "",
      work_years: profile.work_years ?? "",
      technical_proficiency: profile.tech_level_std || "",
      tech_level_std: profile.tech_level_std || "",
      target_roles: profile.target_role_std ? [profile.target_role_std] : [],
      target_role_std: profile.target_role_std || "",
      target_role_raw: profile.target_role_raw || "",
      completed_modules: Array.isArray(profile.completed_courses) ? profile.completed_courses.join(", ") : "",
      completed_courses: Array.isArray(profile.completed_courses) ? profile.completed_courses : [],
      application_type: "",
      finance_knowledge: "",
      parsed_lifecycle_stage: lifecycle,
    },
  };
}

export async function getProfile() {
  const response = await fetch(buildUrl("/profile"), {
    headers: getAuthHeaders(),
  });

  if (response.status === 404) {
    return null;
  }

  return handleResponse(response);
}

export async function updateProfile(data) {
  const response = await fetch(buildUrl("/profile"), {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
      ...getAuthHeaders(),
    },
    body: JSON.stringify(data),
  });

  if (response.status === 404) {
    const createResponse = await fetch(buildUrl("/profile"), {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...getAuthHeaders(),
      },
      body: JSON.stringify(data),
    });

    return handleResponse(createResponse);
  }

  return handleResponse(response);
}

export async function createProfile(data) {
  const response = await fetch(buildUrl("/profile"), {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...getAuthHeaders(),
    },
    body: JSON.stringify(data),
  });

  return handleResponse(response);
}

export async function getChecklist() {
  const response = await fetch(buildUrl("/checklist"), {
    headers: getAuthHeaders(),
  });
  return handleResponse(response);
}

export async function uploadChecklistItemFile(itemId, file) {
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch(buildUrl(`/checklist/items/${encodeURIComponent(itemId)}/file`), {
    method: "POST",
    headers: getAuthHeaders(),
    body: formData,
  });

  return handleResponse(response);
}

