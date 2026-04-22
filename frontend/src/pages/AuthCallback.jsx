import React, { useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { toast } from "sonner";

export default function AuthCallback() {
  const { exchangeSession } = useAuth();
  const navigate = useNavigate();
  const done = useRef(false);

  useEffect(() => {
    if (done.current) return;
    done.current = true;

    const hash = window.location.hash || "";
    const m = hash.match(/session_id=([^&]+)/);
    const sessionId = m ? decodeURIComponent(m[1]) : "";
    if (!sessionId) {
      navigate("/login", { replace: true });
      return;
    }
    (async () => {
      try {
        await exchangeSession(sessionId);
        // clean hash from URL, redirect to dashboard
        window.history.replaceState({}, "", window.location.pathname);
        toast.success("Signed in with Google");
        navigate("/droplets", { replace: true });
      } catch (e) {
        toast.error("Google sign-in failed");
        navigate("/login", { replace: true });
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="min-h-screen flex items-center justify-center text-neutral-400 font-mono text-sm">
      Completing sign-in…
    </div>
  );
}
