import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { SESSION_EXPIRED_EVENT, getMe } from "../../api";

const RoleContext = createContext(null);

function readStoredUser() {
  try {
    const stored = localStorage.getItem("user");
    return stored ? JSON.parse(stored) : null;
  } catch {
    return null;
  }
}

function clearStoredSession() {
  localStorage.removeItem("token");
  localStorage.removeItem("user");
  localStorage.removeItem("role");
}

function storeUser(user) {
  localStorage.setItem("user", JSON.stringify(user));
  localStorage.setItem("role", user.role);
}

export function RoleProvider({ children }) {
  const [loading, setLoading] = useState(true);
  const [profile, setProfile] = useState(null);
  // Set when the server rejected the stored token, so the login page can
  // say why the user landed there.
  const [sessionExpired, setSessionExpired] = useState(false);

  // Any request answered 401 while a token is stored means that token is
  // no longer valid: drop it, and the protected routes send the user to
  // the login page.
  useEffect(() => {
    const expire = () => {
      clearStoredSession();
      setProfile(null);
      setSessionExpired(true);
    };
    window.addEventListener(SESSION_EXPIRED_EVENT, expire);
    return () => window.removeEventListener(SESSION_EXPIRED_EVENT, expire);
  }, []);

  // The stored user is shown straight away, then refreshed from
  // GET /auth/me: the lifecycle stage (and so the derived role) can change
  // on the server, e.g. when a prospect binds their application.
  const refreshUser = useCallback(async () => {
    try {
      const me = await getMe();
      storeUser(me);
      setProfile(me);
    } catch (err) {
      console.error("Unable to refresh the current user:", err);
    }
  }, []);

  useEffect(() => {
    const token = localStorage.getItem("token");
    const stored = readStoredUser();
    if (token && stored) {
      setProfile({ ...stored, role: localStorage.getItem("role") || stored.role });
      refreshUser().finally(() => setLoading(false));
    } else {
      setLoading(false);
    }
  }, [refreshUser]);

  // For endpoints that return the refreshed user themselves.
  const setCurrentUser = useCallback((me) => {
    storeUser(me);
    setProfile(me);
  }, []);

  const login = ({ access_token, user }) => {
    localStorage.setItem("token", access_token);
    storeUser(user);
    setProfile(user);
    setSessionExpired(false);
  };

  const logout = (navigate) => {
    clearStoredSession();
    setProfile(null);
    navigate("/login");
  };

  const user = useMemo(() => {
    if (!profile) return null;
    const name = profile.full_name || profile.email;
    const avatar = name
      .split(" ")
      .map((p) => p[0])
      .slice(0, 2)
      .join("")
      .toUpperCase();
    return {
      id: profile.user_id,
      name,
      email: profile.email,
      role: profile.role,
      lifecycleStage: profile.lifecycle_stage || null,
      policyStage: profile.policy_stage || profile.lifecycle_stage || "prospect",
      onboardingStatus: profile.onboarding_status || null,
      avatar,
    };
  }, [profile]);

  const value = useMemo(
    () => ({
      user,
      role: profile?.role || null,
      lifecycleStage: profile?.lifecycle_stage || null,
      // How the assistant serves the user (backend app/core/stage_policy.py).
      policyStage: profile?.policy_stage || profile?.lifecycle_stage || "prospect",
      loading,
      sessionExpired,
      isStaff: profile?.role === "admin",
      login,
      logout,
      refreshUser,
      setCurrentUser,
    }),
    [user, profile, loading, sessionExpired, refreshUser, setCurrentUser],
  );

  return <RoleContext.Provider value={value}>{children}</RoleContext.Provider>;
}

export function useRole() {
  const context = useContext(RoleContext);
  if (!context) {
    throw new Error("useRole must be used within RoleProvider");
  }
  return context;
}
