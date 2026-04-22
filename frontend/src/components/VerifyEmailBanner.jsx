import React, { useState } from "react";
import { useAuth } from "../context/AuthContext";
import { api } from "../lib/api";
import { Button } from "./ui/button";
import { Warning, X } from "@phosphor-icons/react";
import { toast } from "sonner";

export default function VerifyEmailBanner() {
  const { user, refresh } = useAuth();
  const [dismissed, setDismissed] = useState(false);
  const [busy, setBusy] = useState(false);

  if (!user) return null;
  if (user.email_verified) return null;
  if (dismissed) return null;

  const resend = async () => {
    setBusy(true);
    try {
      const { data } = await api.post("/auth/resend-verification");
      if (data.sent) {
        toast.success("Verification email sent");
      } else {
        toast.info("Verification link logged (email delivery disabled)");
      }
      await refresh();
    } catch {
      toast.error("Failed to send verification");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div
      className="bg-amber-500/10 border-b border-amber-500/30 px-6 py-2.5 flex items-center justify-between gap-4"
      data-testid="verify-banner"
    >
      <div className="flex items-center gap-3 min-w-0">
        <Warning size={16} className="text-amber-400 flex-shrink-0" weight="fill" />
        <div className="text-xs text-amber-200 truncate">
          Verify your email <span className="font-mono text-amber-300">{user.email}</span> to secure your account.
        </div>
      </div>
      <div className="flex items-center gap-2 flex-shrink-0">
        <Button
          size="sm"
          onClick={resend}
          disabled={busy}
          className="h-7 text-xs rounded-none bg-amber-500 hover:bg-amber-400 text-black font-medium"
          data-testid="resend-verification"
        >
          {busy ? "Sending…" : "Resend email"}
        </Button>
        <button
          onClick={() => setDismissed(true)}
          className="text-amber-200/60 hover:text-amber-200 p-1"
          aria-label="Dismiss"
          data-testid="dismiss-banner"
        >
          <X size={14} />
        </button>
      </div>
    </div>
  );
}
