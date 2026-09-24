import { useState } from "react";

interface User {
  id: string;
  name: string;
  username: string;
}

const AUTH_KEY = "percepta_auth_session";

export function useAuth() {
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(() => {
    return localStorage.getItem(AUTH_KEY) === "true";
  });
  const [isLoading, setIsLoading] = useState<boolean>(false);

  const [user, setUser] = useState<User | null>(() => {
    if (localStorage.getItem(AUTH_KEY) === "true") {
      return {
        id: "admin-01",
        name: "Security Commander",
        username: "admin@123",
      };
    }
    return null;
  });

  const signIn = async (username: string, password: string): Promise<boolean> => {
    setIsLoading(true);
    await new Promise((resolve) => setTimeout(resolve, 400));
    if (username.trim() === "admin@123" && password.trim() === "admin@123") {
      localStorage.setItem(AUTH_KEY, "true");
      setIsAuthenticated(true);
      setUser({
        id: "admin-01",
        name: "Security Commander",
        username: "admin@123",
      });
      setIsLoading(false);
      return true;
    } else {
      setIsLoading(false);
      throw new Error("Invalid username or password. Please use admin@123");
    }
  };

  const signOut = async () => {
    localStorage.removeItem(AUTH_KEY);
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
