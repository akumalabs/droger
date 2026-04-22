import React, { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { toast } from "sonner";
import { GoogleLogo, ArrowRight, CircleNotch } from "@phosphor-icons/react";

function formatError(detail) {
  if (!detail) return "Something went wrong";
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail))
    return detail.map((e) => (e?.msg ? e.msg : JSON.stringify(e))).join(", ");
  if (detail?.msg) return detail.msg;
  return String(detail);
}

export default function Login() {
  const { login, loginWithGoogle } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const navigate = useNavigate();

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      await login(email, password);
      toast.success("Welcome back");
      navigate("/droplets");
    } catch (err) {
      toast.error(formatError(err?.response?.data?.detail));
    } finally {
      setBusy(false);
    }
  };

  return (
    <AuthShell heading="Sign in to control room">
      {/* REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH */}
      <Button
        type="button"
        onClick={loginWithGoogle}
        className="w-full rounded-none h-12 bg-white text-black hover:bg-neutral-200 font-medium"
        data-testid="google-login-button"
      >
        <GoogleLogo size={18} weight="bold" className="mr-2" />
        Continue with Google
      </Button>

      <div className="flex items-center gap-3 my-6 text-xs text-neutral-500">
        <div className="flex-1 h-px bg-white/10" />
        <span>OR EMAIL</span>
        <div className="flex-1 h-px bg-white/10" />
      </div>

      <form onSubmit={submit} className="space-y-4" data-testid="login-form">
        <div className="space-y-2">
          <Label className="overline">Email</Label>
          <Input
            data-testid="login-email"
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
            data-testid="login-password"
            type="password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="bg-black border-white/10 rounded-none font-mono h-11"
          />
        </div>
        <Button
          type="submit"
          disabled={busy}
          data-testid="login-submit"
          className="w-full h-12 rounded-none bg-accent-brand text-black hover:bg-cyan-300"
          style={{ background: "#00E5FF", color: "#000" }}
        >
          {busy ? (
            <span className="flex items-center gap-2">
              <CircleNotch className="animate-spin" size={16} /> Signing in
            </span>
          ) : (
            <span className="flex items-center gap-2">
              Sign in <ArrowRight size={16} weight="bold" />
            </span>
          )}
        </Button>
      </form>

      <div className="flex items-center justify-between text-sm text-neutral-400 mt-6">
        <Link to="/forgot-password" className="text-neutral-400 hover:text-accent-brand" data-testid="goto-forgot">
          Forgot password?
        </Link>
        <Link to="/register" className="text-accent-brand hover:underline" data-testid="goto-register">
          Create an account
        </Link>
      </div>
    </AuthShell>
  );
}

export function AuthShell({ heading, children }) {
  return (
    <div className="relative min-h-screen overflow-hidden">
      <div
        className="absolute inset-0 bg-cover bg-center opacity-25"
        style={{
          backgroundImage:
            "url(https://images.pexels.com/photos/29333569/pexels-photo-29333569.jpeg?auto=compress&cs=tinysrgb&dpr=2&h=650&w=940)",
        }}
      />
      <div className="absolute inset-0 bg-black/80 dotted-bg" />
      <div className="relative z-10 min-h-screen grid lg:grid-cols-2">
        <div className="hidden lg:flex flex-col justify-between p-16 border-r border-white/10">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 bg-white text-black flex items-center justify-center font-black font-heading">
              DM
            </div>
            <span className="overline">DROPLET // MANAGER</span>
          </div>
          <div className="max-w-xl">
            <p className="overline mb-6 text-accent-brand">CONTROL ROOM / v2.0</p>
            <h1 className="font-heading font-black text-6xl lg:text-7xl leading-[0.95] tracking-tight mb-6">
              Many tokens.<br />One console.
            </h1>
            <p className="text-neutral-300 text-base md:text-lg leading-relaxed">
              Save every DigitalOcean account under one login, switch with a
              click, and deploy Windows on any droplet with a single wizard.
            </p>
          </div>
          <div className="text-xs font-mono text-neutral-500">
            TOKENS ENCRYPTED AT REST · YOUR ACCOUNTS, YOUR CONTROL
          </div>
        </div>
        <div className="flex items-center justify-center p-6 sm:p-10 lg:p-16">
          <div className="w-full max-w-md border border-white/10 bg-[#0a0a0b] p-8">
            <div className="flex items-center gap-2 lg:hidden mb-4">
              <div className="w-7 h-7 bg-white text-black flex items-center justify-center font-black font-heading text-sm">
                DM
              </div>
              <span className="overline">DROPLET // MANAGER</span>
            </div>
            <h2 className="font-heading text-3xl font-bold mb-6">{heading}</h2>
            {children}
          </div>
        </div>
      </div>
    </div>
  );
}
