// import { createContext, useContext, useMemo, useState } from "react";
// import { ROLES, demoUsers } from "../data/roles";

// const RoleContext = createContext(null);

// export function RoleProvider({ children }) {
//   const [role, setRole] = useState(null);
//   const [user, setUser] = useState(null);

//   const loginAs = (r) => {
//     setRole(r);
//     setUser(demoUsers[r]);
//   };

//   const logout = () => {
//     setRole(null);
//     setUser(null);
//   };

//   const value = useMemo(
//     () => ({ role, user, loginAs, logout, isStaff: role === ROLES.STAFF }),
//     [role, user],
//   );

//   return <RoleContext.Provider value={value}>{children}</RoleContext.Provider>;
// }

// export function useRole() {
//   const ctx = useContext(RoleContext);
//   if (!ctx) throw new Error("useRole must be used within RoleProvider");
//   return ctx;
// }
import { createContext, useContext, useEffect, useMemo, useState } from "react";

const RoleContext = createContext(null);

export function RoleProvider({ children }) {
  const [loading, setLoading] = useState(true);
  const [session, setSession] = useState(null);
  const [profile, setProfile] = useState(null);

  useEffect(() => {
    const token = localStorage.getItem("token");
    let user = null;

try {
  const storedUser = localStorage.getItem("user");
  user = storedUser ? JSON.parse(storedUser) : null;
} catch (err) {
  console.error("Invalid user data in localStorage");
}

    const role = localStorage.getItem("role");

    if (token && user) {
      setSession({
        access_token: token,
        user,
      });

      setProfile({
        ...user,
        role,
      });
    }

    setLoading(false);
  }, []);

  const login = ({ access_token, user, role }) => {
    localStorage.setItem("token", access_token);
    localStorage.setItem("user", JSON.stringify(user));
    localStorage.setItem("role", role);

    setSession({
      access_token: access_token,
      user,
    });

    setProfile({
      ...user,
      role,
    });
  };

  const logout = (navigate) => {
    localStorage.removeItem("token");
    localStorage.removeItem("user");
    localStorage.removeItem("role");

    setSession(null);
    setProfile(null);

    navigate("/login");
  };

  const user = useMemo(() => {
    if (!profile) return null;

    const name =
      profile.full_name ||
      profile.name ||
      profile.email;

    const initials = name
      .split(" ")
      .map((p) => p[0])
      .slice(0, 2)
      .join("")
      .toUpperCase();

    return {
      id: profile.id,
      name,
      email: profile.email,
      role: profile.role,
      avatar: initials,
      headline:
        profile.department ||
        profile.lifecycle_stage ||
        "",
    };
  }, [profile]);

  const value = useMemo(
    () => ({
      session,
      user,
      role: profile?.role || null,
      loading,

      isAdmin:
        profile?.role === "System Admin",

      isStaff: [
        "System Admin",
        "Admissions Staff",
        "Career Advisor",
        "Program Office",
        "Faculty Support",
      ].includes(profile?.role),

      isStudent: [
        "Applicant",
        "Prospective Student",
        "Admitted Student",
        "Enrolled Student",
        "Graduating Student",
        "Alumni",
      ].includes(profile?.role),

      logout,
      login,
    }),
    [session, user, profile, loading]
  );

  return (
    <RoleContext.Provider value={value}>
      {children}
    </RoleContext.Provider>
  );
}

export function useRole() {
  const context = useContext(RoleContext);

  if (!context) {
    throw new Error(
      "useRole must be used within RoleProvider"
    );
  }

  return context;
}