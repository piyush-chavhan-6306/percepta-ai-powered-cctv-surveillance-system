import { useState } from "react";

interface User {
  id: string;
  name: string;
  username: string;
}

const AUTH_KEY = "percepta_auth_session";
const C2_KEY = "percepta_c2_session";

export function useAuth() {
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(() => {
    return (
      localStorage.getItem(AUTH_KEY) === "true" ||
      Boolean(localStorage.getItem(C2_KEY))
    );
  });
  const [isLoading, setIsLoading] = useState<boolean>(false);

  const [user, setUser] = useState<User | null>(() => {
    const raw = localStorage.getItem(C2_KEY);
    if (raw) {
      try {
        const parsed = JSON.parse(raw);
        if (parsed.user) {
          return {
            id: parsed.user.id || "admin-01",
            name: parsed.user.operatorCallsign || parsed.user.email || "Operator",
            username: parsed.user.email || "operator",
          };
        }
      } catch {}
    }
    if (localStorage.getItem(AUTH_KEY) === "true") {
      return {
        id: "admin-01",
        name: "Security Commander",
        username: "operator",
      };
    }
    return null;
  });

  const signIn = async (username: string, password: string): Promise<boolean> => {
    setIsLoading(true);
    await new Promise((resolve) => setTimeout(resolve, 300));
    const u = username.trim().toLowerCase();
    const p = password.trim();

    if (
      (u === "operator" && p === "operator123") ||
      (u === "admin" && p === "admin123") ||
      (u === "commander" && p === "commander123") ||
      (u === "admin@123" && p === "admin@123")
    ) {
      localStorage.setItem(AUTH_KEY, "true");
      const c2Session = {
        user: {
          id: `usr_${u}`,
          email: `${u}@percepta.mil`,
          role: "TACTICAL_OPERATOR",
          operatorCallsign: `${u.toUpperCase()}-PRIMARY`,
        },
        access_token: `tok_live_${Date.now()}`,
      };
      localStorage.setItem(C2_KEY, JSON.stringify(c2Session));
      setIsAuthenticated(true);
      setUser({
        id: `usr_${u}`,
        name: `${u.toUpperCase()} Duty Officer`,
        username: u,
      });
      setIsLoading(false);
      return true;
    } else {
      setIsLoading(false);
      throw new Error("Invalid username or password. Default operator credentials: operator / operator123");
    }
  };

  const signOut = async () => {
    localStorage.removeItem(AUTH_KEY);
    localStorage.removeItem(C2_KEY);
    setIsAuthenticated(false);
    setUser(null);
  };

  return {
    user,
    isAuthenticated,
    isLoading,
    signIn,
    signOut,
  };
}
