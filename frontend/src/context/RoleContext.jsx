import { createContext, useContext, useMemo, useState } from "react";
import { ROLES, demoUsers } from "../data/roles";

const RoleContext = createContext(null);

export function RoleProvider({ children }) {
  const [role, setRole] = useState(null);
  const [user, setUser] = useState(null);

  const loginAs = (r) => {
    setRole(r);
    setUser(demoUsers[r]);
  };

  const logout = () => {
    setRole(null);
    setUser(null);
  };

  const value = useMemo(
    () => ({ role, user, loginAs, logout, isStaff: role === ROLES.STAFF }),
    [role, user],
  );

  return <RoleContext.Provider value={value}>{children}</RoleContext.Provider>;
}

export function useRole() {
  const ctx = useContext(RoleContext);
  if (!ctx) throw new Error("useRole must be used within RoleProvider");
  return ctx;
}
