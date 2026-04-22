import React, { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { AuthShell } from "./Login";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { toast } from "sonner";
import { GoogleLogo, ArrowRight, CircleNotch } from "@phosphor-icons/react";

function fmt(detail) {
  if (!detail) return "Something went wrong";
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail))
    return detail.map((e) => (e?.msg ? e.msg : JSON.stringify(e))).join(", ");
  if (detail?.msg) return detail.msg;
  return String(detail);
}

export default function Register() {
  const { register, loginWithGoogle } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
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
      await register(email, password, name);
      toast.success("Account created");
      navigate("/droplets");
    } catch (err) {
      toast.error(fmt(err?.response?.data?.detail));
    } finally {
      setBusy(false);
    }
  };

  return (
    <AuthShell heading="Create your account">
      {/* REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH */}
      <Button
        type="button"
        onClick={loginWithGoogle}
        className="w-full rounded-none h-12 bg-white text-black hover:bg-neutral-200 font-medium"
        data-testid="google-register-button"
      >
        <GoogleLogo size={18} weight="bold" className="mr-2" />
        Sign up with Google
      </Button>

      <div className="flex items-center gap-3 my-6 text-xs text-neutral-500">
        <div className="flex-1 h-px bg-white/10" />
        <span>OR EMAIL</span>
        <div className="flex-1 h-px bg-white/10" />
      </div>

      <form onSubmit={submit} className="space-y-4" data-testid="register-form">
        <div className="space-y-2">
          <Label className="overline">Display Name</Label>
          <Input
            data-testid="register-name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="bg-black border-white/10 rounded-none font-mono h-11"
          />
        </div>
        <div className="space-y-2">
          <Label className="overline">Email</Label>
          <Input
            data-testid="register-email"
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="bg-black border-white/10 rounded-none font-mono h-11"
          />
        </div>
        <div className="space-y-2">
          <Label className="overline">Password</Label>
          <Input
            data-testid="register-password"
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
          data-testid="register-submit"
          className="w-full h-12 rounded-none"
          style={{ background: "#00E5FF", color: "#000" }}
        >
          {busy ? (
            <span className="flex items-center gap-2">
              <CircleNotch className="animate-spin" size={16} /> Creating
            </span>
          ) : (
            <span className="flex items-center gap-2">
              Create account <ArrowRight size={16} weight="bold" />
            </span>
          )}
        </Button>
      </form>

      <p className="text-sm text-neutral-400 mt-6">
        Already have an account?{" "}
        <Link to="/login" className="text-accent-brand hover:underline" data-testid="goto-login">
          Sign in
        </Link>
      </p>
    </AuthShell>
  );
}
