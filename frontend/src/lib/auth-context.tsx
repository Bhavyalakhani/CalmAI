// auth context - provides current user, login/logout, token management
// wraps the entire app to give all pages access to auth state

"use client";

import {
  createContext,
  useContext,
  useEffect,
  useState,
  useCallback,
  type ReactNode,
} from "react";
import { useRouter, usePathname } from "next/navigation";
import type { Therapist, Patient, UserRole } from "@/types";
import {
  login as apiLogin,
  signup as apiSignup,
  getMe,
  logout as apiLogout,
  getAccessToken,
  clearTokens,
  type SignupPayload,
} from "@/lib/api";

// auth context types

interface AuthContextType {
  user: Therapist | Patient | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  login: (email: string, password: string) => Promise<void>;
  signup: (payload: SignupPayload) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType>({
  user: null,
  isLoading: true,
  isAuthenticated: false,
  login: async () => {},
  signup: async () => {},
  logout: () => {},
});

// public routes that don't require auth
const PUBLIC_ROUTES = ["/", "/login", "/signup"];

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<Therapist | Patient | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const router = useRouter();
  const pathname = usePathname();

  // check auth state on mount
  useEffect(() => {
    const checkAuth = async () => {
      const token = getAccessToken();
      if (!token) {
        setIsLoading(false);
        return;
      }

      try {
        const me = await getMe();
        setUser(me);
      } catch {
        clearTokens();
      } finally {
        setIsLoading(false);
      }
    };

    checkAuth();
  }, []);

  // redirect unauthenticated users away from protected routes
  // redirect wrong roles to their correct area
  // clear tokens when user visits login/signup (fresh session)
  useEffect(() => {
    if (isLoading) return;

    const isPublic = PUBLIC_ROUTES.includes(pathname);

    // if user lands on login/signup with a stale token, clear it
    if ((pathname === "/login" || pathname === "/signup") && !user) {
      clearTokens();
    }

    // unauthenticated on protected route -> login
    if (!user && !isPublic) {
      router.push("/login");
      return;
    }

    // role-based route guards
    if (user) {
      const isDashboard = pathname.startsWith("/dashboard");
      const isJournal = pathname.startsWith("/journal");

      // therapists cannot access journal routes
      if (user.role === "therapist" && isJournal) {
        router.push("/dashboard");
        return;
      }

      // patients cannot access dashboard routes
      if (user.role === "patient" && isDashboard) {
        router.push("/journal");
        return;
      }

      // authenticated user on login/signup -> redirect to their home
      if (pathname === "/login" || pathname === "/signup") {
        router.push(user.role === "therapist" ? "/dashboard" : "/journal");
        return;
      }
    }
  }, [user, isLoading, pathname, router]);

  const login = useCallback(
    async (email: string, password: string) => {
      await apiLogin(email, password);
      const me = await getMe();
      setUser(me);

      // redirect based on role
      if (me.role === "therapist") {
        router.push("/dashboard");
      } else {
        router.push("/journal");
      }
    },
    [router]
  );

  const signup = useCallback(
    async (payload: SignupPayload) => {
      await apiSignup(payload);
      const me = await getMe();
      setUser(me);

      if (me.role === "therapist") {
        router.push("/dashboard");
      } else {
        router.push("/journal");
      }
    },
    [router]
  );

  const logout = useCallback(() => {
    setUser(null);
    apiLogout();
  }, []);

  return (
    <AuthContext.Provider
      value={{
        user,
        isLoading,
        isAuthenticated: !!user,
        login,
        signup,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
