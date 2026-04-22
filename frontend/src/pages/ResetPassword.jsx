import React, { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { api } from "../lib/api";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { AuthShell } from "./Login";
import { toast } from "sonner";
import { ArrowRight, CircleNotch } from "@phosphor-icons/react";

export default function ResetPassword() {
  const [params] = useSearchParams();
  const token = params.get("token") || "";
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const navigate = useNavigate();

  const submit = async (e) => {
    e.preventDefault();
    if (password.length < 6) {
      toast.error("Password must be at least 6 characters");
      return;
    }
    setBusy(true);
    try {
      await api.post("/auth/reset-password", { token, password });
      toast.success("Password updated — sign in");
      navigate("/login", { replace: true });
    } catch (e) {
      toast.error(
        typeof e?.response?.data?.detail === "string"
          ? e.response.data.detail
          : "Reset failed",
      );
    } finally {
      setBusy(false);
    }
  };

  if (!token) {
    return (
      <AuthShell heading="Invalid reset link">
        <p className="text-sm text-neutral-400 mb-6">
          The link is missing or malformed. Request a new one below.
        </p>
        <Link to="/forgot-password">
          <Button
            className="w-full h-12 rounded-none"
            style={{ background: "#00E5FF", color: "#000" }}
          >
            Request new link
          </Button>
        </Link>
      </AuthShell>
    );
  }

  return (
    <AuthShell heading="Choose a new password">
      <form onSubmit={submit} className="space-y-4" data-testid="reset-form">
        <div className="space-y-2">
          <Label className="overline">New Password</Label>
          <Input
            data-testid="reset-password"
            type="password"
            required
            minLength={6}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="bg-black border-white/10 rounded-none font-mono h-11"
          />
          <p className="text-xs text-neutral-500">Minimum 6 characters.</p>
        </div>
        <Button
          type="submit"
          disabled={busy}
          data-testid="reset-submit"
          className="w-full h-12 rounded-none"
          style={{ background: "#00E5FF", color: "#000" }}
        >
          {busy ? (
            <span className="flex items-center gap-2">
              <CircleNotch className="animate-spin" size={14} /> Updating
            </span>
          ) : (
            <span className="flex items-center gap-2">
              Update password <ArrowRight size={14} weight="bold" />
            </span>
          )}
        </Button>
      </form>
    </AuthShell>
  );
}
