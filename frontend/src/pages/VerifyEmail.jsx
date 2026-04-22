import React, { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api } from "../lib/api";
import { CircleNotch, CheckCircle, XCircle, ArrowRight } from "@phosphor-icons/react";
import { Button } from "../components/ui/button";
import { AuthShell } from "./Login";

export default function VerifyEmail() {
  const [params] = useSearchParams();
  const [state, setState] = useState("loading"); // loading | ok | error
  const [message, setMessage] = useState("");

  useEffect(() => {
    const token = params.get("token");
    if (!token) {
      setState("error");
      setMessage("Missing verification token.");
      return;
    }
    (async () => {
      try {
        await api.post("/auth/verify-email", { token });
        setState("ok");
      } catch (e) {
        setState("error");
        setMessage(
          typeof e?.response?.data?.detail === "string"
            ? e.response.data.detail
            : "Verification failed",
        );
      }
    })();
  }, [params]);

  return (
    <AuthShell heading="Email verification">
      {state === "loading" && (
        <div className="flex items-center gap-3 text-neutral-400" data-testid="verify-loading">
          <CircleNotch className="animate-spin" size={18} /> Verifying your email…
        </div>
      )}
      {state === "ok" && (
        <div className="space-y-6" data-testid="verify-ok">
          <div className="flex items-center gap-3 text-green-400">
            <CheckCircle size={24} weight="fill" />
            <span className="font-heading text-xl font-bold">Email verified</span>
          </div>
          <p className="text-sm text-neutral-400">
            You're all set. You can close this tab or head back to the app.
          </p>
          <Link to="/droplets">
            <Button
              className="w-full h-12 rounded-none"
              style={{ background: "#00E5FF", color: "#000" }}
              data-testid="verify-continue"
            >
              Continue to app <ArrowRight size={14} weight="bold" className="ml-2" />
            </Button>
          </Link>
        </div>
      )}
      {state === "error" && (
        <div className="space-y-6" data-testid="verify-error">
          <div className="flex items-center gap-3 text-red-400">
            <XCircle size={24} weight="fill" />
            <span className="font-heading text-xl font-bold">Verification failed</span>
          </div>
          <p className="text-sm text-neutral-400">{message}</p>
          <Link to="/droplets">
            <Button
              variant="outline"
              className="w-full h-12 rounded-none border-white/10"
            >
              Back to app
            </Button>
          </Link>
        </div>
      )}
    </AuthShell>
  );
}
