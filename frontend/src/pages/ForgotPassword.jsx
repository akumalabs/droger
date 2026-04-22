import React, { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../lib/api";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { AuthShell } from "./Login";
import { toast } from "sonner";
import { ArrowRight, CircleNotch, Envelope } from "@phosphor-icons/react";

export default function ForgotPassword() {
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [sent, setSent] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      await api.post("/auth/forgot-password", { email });
      setSent(true);
    } catch {
      toast.error("Something went wrong");
    } finally {
      setBusy(false);
    }
  };

  return (
    <AuthShell heading="Reset your password">
      {sent ? (
        <div className="space-y-6" data-testid="forgot-sent">
          <div className="flex items-center gap-3 text-accent-brand">
            <Envelope size={22} weight="fill" />
            <span className="font-heading text-xl font-bold">Check your inbox</span>
          </div>
          <p className="text-sm text-neutral-400">
            If an account exists for{" "}
            <span className="font-mono text-white">{email}</span>, we sent a
            reset link. The link expires in 1 hour.
          </p>
          <Link to="/login">
            <Button
              variant="outline"
              className="w-full h-12 rounded-none border-white/10"
            >
              Back to sign in
            </Button>
          </Link>
        </div>
      ) : (
        <form onSubmit={submit} className="space-y-4" data-testid="forgot-form">
          <p className="text-sm text-neutral-400">
            Enter the email you registered with and we'll send you a reset
            link.
          </p>
          <div className="space-y-2">
            <Label className="overline">Email</Label>
            <Input
              data-testid="forgot-email"
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="bg-black border-white/10 rounded-none font-mono h-11"
            />
          </div>
          <Button
            type="submit"
            disabled={busy}
            data-testid="forgot-submit"
            className="w-full h-12 rounded-none"
            style={{ background: "#00E5FF", color: "#000" }}
          >
            {busy ? (
              <span className="flex items-center gap-2">
                <CircleNotch className="animate-spin" size={14} /> Sending
              </span>
            ) : (
              <span className="flex items-center gap-2">
                Send reset link <ArrowRight size={14} weight="bold" />
              </span>
            )}
          </Button>
          <p className="text-sm text-neutral-400 text-center pt-2">
            <Link to="/login" className="text-accent-brand hover:underline">
              Back to sign in
            </Link>
          </p>
        </form>
      )}
    </AuthShell>
  );
}
