import { useEffect } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { create } from "zustand";
import { api, setAccountId } from "./api";
import type { Session } from "./types";

type State = {
  session: Session | null;
  ended: boolean;
  setSession: (session: Session | null) => void;
  end: () => void;
};
function locked() {
  try {
    return localStorage.getItem("shiftproof-locked") === "true";
  } catch {
    return false;
  }
}
export const useSession = create<State>((set) => ({
  session: null,
  ended: locked(),
  setSession: (session) => {
    setAccountId(session?.user.id || null);
    try {
      if (session) localStorage.setItem("shiftproof-account", session.user.id);
    } catch {
      /* Session still works in memory. */
    }
    set({ session, ended: false });
  },
  end: () => {
    setAccountId(null);
    set({ session: null, ended: true });
  },
}));

export function useSessionBootstrap() {
  const { session, setSession, end, ended } = useSession();
  const client = useQueryClient();
  const query = useQuery({
    queryKey: ["session"],
    queryFn: () => api<Session>("/auth/me"),
    retry: false,
    staleTime: 60_000,
    enabled: !ended,
  });
  useEffect(() => {
    if (query.data && !ended) setSession(query.data);
  }, [query.data, setSession, ended]);
  useEffect(() => {
    const expire = () => {
      end();
      client.clear();
    };
    const sharedDevice = (event: StorageEvent) => {
      const current = useSession.getState().session;
      if (
        (event.key === "shiftproof-locked" && event.newValue === "true") ||
        (event.key === "shiftproof-account" &&
          current &&
          event.newValue !== current.user.id)
      )
        expire();
    };
    window.addEventListener("shiftproof-session-ended", expire);
    window.addEventListener("storage", sharedDevice);
    return () => {
      window.removeEventListener("shiftproof-session-ended", expire);
      window.removeEventListener("storage", sharedDevice);
    };
  }, [end, client]);
  useEffect(() => {
    if (!session) return;
    let lastActivity = Date.now();
    const active = () => {
      lastActivity = Date.now();
    };
    const timer = window.setInterval(() => {
      if (
        Date.now() >= Date.parse(session.session.expiresAt) ||
        Date.now() - lastActivity > session.session.idleMinutes * 60_000
      ) {
        end();
        client.clear();
      }
    }, 5000);
    window.addEventListener("pointerdown", active);
    window.addEventListener("keydown", active);
    return () => {
      clearInterval(timer);
      window.removeEventListener("pointerdown", active);
      window.removeEventListener("keydown", active);
    };
  }, [session?.user.id, session?.session.expiresAt, end, client]);
  return { ...query, session, ended };
}

export function useSignOut() {
  const client = useQueryClient();
  const end = useSession((state) => state.end);
  return async () => {
    const revocation = api("/auth/logout", {
      method: "POST",
      body: "{}",
      keepalive: true,
    }).catch(() => undefined);
    // Hide the previous person's workspace immediately, including when offline.
    try {
      localStorage.setItem("shiftproof-locked", "true");
    } catch {
      /* Memory state still clears. */
    }
    end();
    client.clear();
    await Promise.race([
      revocation,
      new Promise((resolve) => setTimeout(resolve, 500)),
    ]);
    window.location.assign("/signin");
  };
}
