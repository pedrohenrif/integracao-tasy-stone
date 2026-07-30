import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { loginApi } from "../api/client";
import type { User } from "../types";

type AuthState = {
  user: User | null;
  token: string | null;
  login: (login: string, password: string) => Promise<void>;
  logout: () => void;
};

const AuthContext = createContext<AuthState | null>(null);

function loadUser(): User | null {
  try {
    const raw = localStorage.getItem("portal_user");
    return raw ? (JSON.parse(raw) as User) : null;
  } catch {
    return null;
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(() => localStorage.getItem("portal_token"));
  const [user, setUser] = useState<User | null>(() => loadUser());

  const login = useCallback(async (loginName: string, password: string) => {
    const data = await loginApi(loginName, password);
    localStorage.setItem("portal_token", data.access_token);
    localStorage.setItem("portal_user", JSON.stringify(data.user));
    setToken(data.access_token);
    setUser(data.user);
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem("portal_token");
    localStorage.removeItem("portal_user");
    setToken(null);
    setUser(null);
  }, []);

  const value = useMemo(
    () => ({ user, token, login, logout }),
    [user, token, login, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth fora do AuthProvider");
  return ctx;
}
